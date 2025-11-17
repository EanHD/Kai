"""
Code Executor Tool - Safe Python code execution in Docker containers.

Implements T076-T079, T082-T084:
- Docker container management with gVisor runtime support
- Security constraints (memory, CPU, network, filesystem)
- Timeout protection and resource limits
- Result parsing and fallback strategies
"""

import asyncio
import hashlib
import logging
from typing import Any

from docker.errors import DockerException, ImageNotFound, NotFound

import docker
from src.tools.base_tool import BaseTool, ToolResult, ToolStatus

logger = logging.getLogger(__name__)


class CodeExecutorTool(BaseTool):
    """Execute Python code in isolated Docker containers."""

    def __init__(self, config: dict[str, Any]):
        """
        Initialize code executor with Docker client.

        Args:
            config: Configuration with security settings
                - timeout_seconds: Max execution time (default: 30)
                - memory_limit: Container memory limit (default: "128m")
                - cpu_quota: CPU quota in microseconds (default: 100000)
                - image: Docker image to use (default: "kai-python-sandbox:latest")
                - use_gvisor: Whether to use gVisor runtime if available (default: True)
                - network_disabled: Disable network in container (default: True)
        """
        super().__init__(config)
        self.timeout_seconds = config.get("timeout_seconds", 30)
        self.memory_limit = config.get("memory_limit", "128m")
        self.cpu_quota = config.get("cpu_quota", 100000)
        self.image = config.get("image", "kai-python-sandbox:latest")
        self.use_gvisor = config.get("use_gvisor", True)
        self.network_disabled = config.get("network_disabled", True)

        # Initialize Docker client
        try:
            self.docker_client = docker.from_env()
            self._verify_image()
            self._detect_gvisor_runtime()
            logger.info(
                f"CodeExecutorTool initialized with image={self.image}, "
                f"gvisor={'enabled' if self.gvisor_available else 'unavailable'}"
            )
        except DockerException as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            if "Permission denied" in str(e):
                logger.error(
                    "Docker permission error. Fix with:\n"
                    "  sudo usermod -aG docker $USER\n"
                    "  sudo chmod 666 /var/run/docker.sock\n"
                    "  newgrp docker\n"
                    "Or run: ./scripts/fix_docker_permissions.sh"
                )
            self.docker_client = None

    def _verify_image(self):
        """Verify Docker image exists, pull if missing."""
        try:
            self.docker_client.images.get(self.image)
            logger.info(f"Docker image {self.image} found")
        except ImageNotFound:
            logger.warning(f"Image {self.image} not found, using python:3.11-slim instead")
            self.image = "python:3.11-slim"
            try:
                self.docker_client.images.pull(self.image)
            except DockerException as e:
                logger.error(f"Failed to pull fallback image: {e}")

    def _detect_gvisor_runtime(self):
        """Check if gVisor runtime is available."""
        self.gvisor_available = False
        if not self.use_gvisor:
            return

        try:
            info = self.docker_client.info()
            runtimes = info.get("Runtimes", {})
            self.gvisor_available = "runsc" in runtimes
            if self.gvisor_available:
                logger.info("gVisor runtime detected and enabled")
            else:
                logger.info("gVisor runtime not available, using default runtime")
        except Exception as e:
            logger.warning(f"Failed to detect gVisor runtime: {e}")

    async def execute(self, parameters: dict[str, Any]) -> ToolResult:
        """
        Execute Python code in sandboxed Docker container.

        Args:
            parameters: Dict with "code" (str) to execute

        Returns:
            ToolResult with stdout/stderr and execution status
        """
        if not self.docker_client:
            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.FAILED,
                error=(
                    "Docker client not available. Please ensure:\n"
                    "1. Docker is installed and running\n"
                    "2. Your user has Docker permissions\n"
                    "Fix with: ./scripts/fix_docker_permissions.sh"
                ),
                fallback_used=True,
            )

        code = parameters.get("code", "").strip()
        if not code:
            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.FAILED,
                error="No code provided for execution",
            )

        # Generate unique container name
        code_hash = hashlib.sha256(code.encode()).hexdigest()[:12]
        container_name = f"kai-exec-{code_hash}"

        try:
            # Execute code with timeout protection
            result = await asyncio.wait_for(
                self._run_code_in_container(code, container_name),
                timeout=self.timeout_seconds,
            )
            return result

        except TimeoutError:
            logger.warning(f"Code execution timed out after {self.timeout_seconds}s")
            # Cleanup timed-out container
            await self._cleanup_container(container_name)
            return self._timeout_fallback(code)

        except Exception as e:
            logger.error(f"Code execution failed: {e}")
            await self._cleanup_container(container_name)
            return self._execution_fallback(code, str(e))

    async def _run_code_in_container(self, code: str, container_name: str) -> ToolResult:
        """
        Run code in Docker container with security constraints.

        Args:
            code: Python code to execute
            container_name: Unique container identifier

        Returns:
            ToolResult with execution output
        """
        # Prepare runtime settings
        runtime = "runsc" if self.gvisor_available else None

        # Security constraints
        security_opt = ["no-new-privileges:true"]
        cap_drop = ["ALL"]

        # Run container with constraints
        container = None
        try:
            container = self.docker_client.containers.run(
                image=self.image,
                command=["python", "-c", code],
                name=container_name,
                detach=True,
                remove=False,  # Manual cleanup for better error handling
                mem_limit=self.memory_limit,
                cpu_quota=self.cpu_quota,
                network_disabled=self.network_disabled,
                read_only=True,  # Read-only root filesystem
                runtime=runtime,
                security_opt=security_opt,
                cap_drop=cap_drop,
                tmpfs={"/tmp": "size=10M,mode=1777"},  # Writable /tmp with size limit
            )

            # Wait for container to finish
            result = container.wait()
            exit_code = result.get("StatusCode", -1)

            # Get output
            logs = container.logs(stdout=True, stderr=True).decode("utf-8")

            # Parse stdout/stderr
            stdout, stderr = self._parse_container_logs(logs)

            # Cleanup
            container.remove(force=True)

            if exit_code == 0:
                return ToolResult(
                    tool_name=self.tool_name,
                    status=ToolStatus.SUCCESS,
                    data={"stdout": stdout, "stderr": stderr, "exit_code": exit_code},
                )
            else:
                return ToolResult(
                    tool_name=self.tool_name,
                    status=ToolStatus.FAILED,
                    error=f"Code execution failed with exit code {exit_code}",
                    data={"stdout": stdout, "stderr": stderr, "exit_code": exit_code},
                )

        except Exception as e:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
            raise e

    def _parse_container_logs(self, logs: str) -> tuple[str, str]:
        """
        Parse container logs into stdout and stderr.

        Args:
            logs: Combined container output

        Returns:
            Tuple of (stdout, stderr)
        """
        # Docker combines stdout/stderr - try to separate errors
        lines = logs.strip().split("\n")
        stdout_lines = []
        stderr_lines = []

        for line in lines:
            if any(err in line.lower() for err in ["error", "traceback", "exception", "warning"]):
                stderr_lines.append(line)
            else:
                stdout_lines.append(line)

        return "\n".join(stdout_lines), "\n".join(stderr_lines)

    async def _cleanup_container(self, container_name: str):
        """Force remove container if it exists."""
        try:
            container = self.docker_client.containers.get(container_name)
            container.remove(force=True)
            logger.info(f"Cleaned up container {container_name}")
        except NotFound:
            pass  # Already removed
        except Exception as e:
            logger.warning(f"Failed to cleanup container {container_name}: {e}")

    def _timeout_fallback(self, code: str) -> ToolResult:
        """
        Fallback when code execution times out.

        Args:
            code: The code that timed out

        Returns:
            ToolResult with timeout error and suggestion
        """
        return ToolResult(
            tool_name=self.tool_name,
            status=ToolStatus.TIMEOUT,
            error=f"Code execution timed out after {self.timeout_seconds}s",
            data={
                "suggestion": "Try simplifying the code or breaking it into smaller steps",
                "code": code[:200],  # Include snippet for context
            },
            fallback_used=True,
        )

    def _execution_fallback(self, code: str, error_msg: str) -> ToolResult:
        """
        Fallback when code execution fails.

        Args:
            code: The code that failed
            error_msg: Error message from execution

        Returns:
            ToolResult with error and potential fixes
        """
        suggestions = []

        # Analyze error for common issues
        if "ModuleNotFoundError" in error_msg or "ImportError" in error_msg:
            suggestions.append(
                "The code tried to import a module that's not available in the sandbox. "
                "Only standard library modules are supported."
            )
        elif "SyntaxError" in error_msg:
            suggestions.append("Check the code syntax for errors.")
        elif "MemoryError" in error_msg:
            suggestions.append("The code used too much memory. Try processing less data.")
        else:
            suggestions.append("Try rewriting the code with error handling.")

        return ToolResult(
            tool_name=self.tool_name,
            status=ToolStatus.FAILED,
            error=f"Code execution failed: {error_msg}",
            data={
                "suggestions": suggestions,
                "code": code[:200],
            },
            fallback_used=True,
        )

    async def fallback(self, parameters: dict[str, Any], error: Exception) -> ToolResult:
        """
        Fallback when Docker is unavailable.

        Args:
            parameters: Original parameters
            error: The error that triggered fallback

        Returns:
            ToolResult explaining Docker unavailability
        """
        return ToolResult(
            tool_name=self.tool_name,
            status=ToolStatus.FAILED,
            error="Code execution unavailable - Docker service is not running",
            data={
                "suggestion": "Start Docker service to enable code execution",
                "original_error": str(error),
            },
            fallback_used=True,
        )
