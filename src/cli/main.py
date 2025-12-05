"""CLI interface for interactive conversation."""

import os
import sys

# Suppress ALL Python warnings via environment variable (affects subprocesses too)
os.environ["PYTHONWARNINGS"] = "ignore"

import asyncio
import uuid
import warnings
from pathlib import Path

# Suppress all warnings in this process
warnings.simplefilter("ignore")

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import logging

from src.agents.reflection_agent import ReflectionAgent
from src.core.conversation_service import ConversationService
from src.core.orchestrator import Orchestrator
from src.core.providers.ollama_provider import OllamaProvider
from src.core.providers.openrouter_provider import OpenRouterProvider
from src.embeddings.factory import get_shared_embeddings_provider
from src.lib.config import ConfigLoader
from src.lib.logger import setup_logging
from src.models.conversation import ConversationSession
from src.storage.memory_vault import MemoryVault
from src.storage.sqlite_store import SQLiteStore
from src.storage.vector_store import VectorStore
from src.tools.code_exec_wrapper import CodeExecWrapper
from src.tools.memory_store import MemoryStoreTool
from src.tools.sentiment_analyzer import SentimentAnalyzerTool
from src.tools.web_search import WebSearchTool
from src.tools.chatgpt_importer import ChatGPTImporter
from src.feedback.rage_trainer import RageTrainer, format_weekly_message

logger = logging.getLogger(__name__)


class CLI:
    """Command-line interface for the LLM orchestrator."""

    def __init__(self, debug: bool = False, show_reflection: bool = False):
        """Initialize CLI.

        Args:
            debug: Enable debug mode with verbose logging
            show_reflection: Show detailed reflection output (reflection always runs in background)
        """
        self.debug = debug
        self.show_reflection = show_reflection

        # Auto-start services before initialization
        self._auto_start_services()

        # Generate user ID first (needed for MemoryVault)
        self.user_id = str(uuid.uuid4())

        # Load configuration
        self.config = ConfigLoader()

        # Setup logging (quiet mode unless debug)
        setup_logging(log_level="DEBUG" if debug else "INFO", structured=False, quiet=not debug)

        # Initialize storage
        sqlite_path = self.config.get_env("sqlite_db_path")
        vector_path = self.config.get_env("vector_db_path")

        self.sqlite_store = SQLiteStore(sqlite_path)
        self.vector_store = VectorStore(vector_path)

        # Initialize services
        self.conversation_service = ConversationService(self.sqlite_store)
        # Memory Vault (file-based, user-owned)
        self.memory_vault = MemoryVault(user_id=self.user_id)

        # Initialize LLM connectors
        self.local_connector = None
        self.external_connectors = {}
        self._init_connectors()

        # Initialize embeddings provider (shared across tools)
        self.embeddings_provider = get_shared_embeddings_provider()
        if self.debug:
            if self.embeddings_provider:
                logger.info("Embeddings provider initialized")
            else:
                logger.info("Embeddings disabled - set OPENROUTER_API_KEY to enable")

        # Initialize tools
        self.tools = self._init_tools()

        # Get cost limits from config
        cost_limit = self.config.get_env("default_cost_limit")
        soft_cap_threshold = self.config.get_env("soft_cap_threshold")

        # Initialize orchestrator
        self.orchestrator = Orchestrator(
            local_connector=self.local_connector,
            external_connectors=self.external_connectors,
            tools=self.tools,
            cost_limit=cost_limit,
            soft_cap_threshold=soft_cap_threshold,
            memory_vault=self.memory_vault,
        )

        # CRITICAL: Inject conversation service for context retention in fast path
        self.orchestrator.conversation_service = self.conversation_service

        # Initialize rage trainer for instant feedback learning
        self.rage_trainer = RageTrainer(self.memory_vault)

        # Initialize reflection agent (always enabled for continuous learning)
        self.reflection_agent = None
        if self.local_connector:
            self.reflection_agent = ReflectionAgent(self.local_connector, self.memory_vault)
            if self.debug:
                logger.info("Reflection agent initialized (always-on background learning)")
        elif self.debug:
            logger.warning("No local connector available - reflection disabled")

        # Current conversation
        self.conversation: ConversationSession | None = None

    def _auto_start_services(self):
        """Auto-start required services (Ollama, Docker)."""
        import subprocess
        import sys

        # Check and start Ollama
        try:
            subprocess.run(
                ["ollama", "list"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
            )
            if not self.debug:
                print("✓ Ollama running")
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
            print("⚠ Ollama not running - attempting to start...")
            try:
                if sys.platform == "darwin":  # macOS
                    subprocess.Popen(
                        ["open", "-a", "Ollama"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:  # Linux
                    subprocess.Popen(
                        ["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                import time

                time.sleep(2)  # Give it a moment to start
                print("✓ Ollama started")
            except Exception as e:
                print(f"⚠ Could not start Ollama automatically: {e}")
                print("  Please start manually: ollama serve")

        # Check and start Docker
        try:
            subprocess.run(
                ["docker", "ps"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
            )
            if not self.debug:
                print("✓ Docker running")
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
            print("⚠ Docker not running - attempting to start...")
            try:
                if sys.platform == "darwin":  # macOS
                    subprocess.Popen(
                        ["open", "-a", "Docker"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                elif sys.platform == "linux":
                    subprocess.Popen(
                        ["sudo", "systemctl", "start", "docker"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                import time

                time.sleep(3)  # Docker takes longer
                print("✓ Docker started")
            except Exception as e:
                print(f"⚠ Could not start Docker automatically: {e}")
                print("  Code execution will use stubs until Docker is running")

    def _init_connectors(self):
        """Initialize LLM connectors from configuration."""
        active_models = self.config.get_active_models()

        for model_config in active_models:
            config_dict = {
                "model_id": model_config.model_id,
                "model_name": model_config.model_name,
                "provider": model_config.provider,
                "capabilities": model_config.capabilities,
                "context_window": model_config.context_window,
                "cost_per_1k_input": model_config.cost_per_1k_input,
                "cost_per_1k_output": model_config.cost_per_1k_output,
            }

            if model_config.provider == "ollama":
                ollama_url = self.config.get_env("ollama_base_url")
                self.local_connector = OllamaProvider(config_dict, ollama_url)
                if self.debug:
                    logger.info(f"Initialized Ollama: {model_config.model_name}")

            elif model_config.provider == "openrouter":
                api_key = self.config.get_env("openrouter_api_key")
                if api_key:
                    connector = OpenRouterProvider(config_dict, api_key)
                    self.external_connectors[model_config.model_id] = connector
                    if self.debug:
                        logger.info(f"Initialized OpenRouter: {model_config.model_name}")
                else:
                    logger.warning(f"No API key for OpenRouter model: {model_config.model_id}")

    def _init_tools(self) -> dict:
        """Initialize available tools based on configuration."""
        tools = {}
        enabled_tools = self.config.get_enabled_tools()

        # Initialize web search tool
        if "web_search" in enabled_tools:
            try:
                tool_config = enabled_tools["web_search"]
                web_search_config = {
                    "max_results": tool_config.config.get("max_results", 10),
                    "timeout_seconds": tool_config.config.get("timeout_seconds", 15),
                    "max_days_old": tool_config.config.get("max_days_old", 30),
                    "api_key": self.config.get_env("brave_api_key"),  # Brave API
                    "tavily_api_key": self.config.get_env("tavily_api_key"),  # Tavily AI
                }
                tools["web_search"] = WebSearchTool(web_search_config)
                if self.debug:
                    logger.info("WebSearchTool initialized with Perplexity-style enhancements")
            except Exception as e:
                logger.error(f"Failed to initialize WebSearchTool: {e}")
        else:
            if self.debug:
                logger.info("WebSearchTool disabled in configuration")

        # Initialize memory store tool
        if "rag" in enabled_tools:
            try:
                encryption_key = self.config.get_env("encryption_key")
                if not encryption_key:
                    raise ValueError("encryption_key not found in config")

                tool_config = enabled_tools["rag"]
                memory_config = {
                    "embedding_model": tool_config.config.get(
                        "embedding_model", self.config.get_env("embedding_model")
                    ),
                }
                tools["rag"] = MemoryStoreTool(
                    config=memory_config,
                    vector_store=self.vector_store,
                    encryption_key=encryption_key,
                    embeddings_provider=self.embeddings_provider,
                )
                if self.debug:
                    logger.info("MemoryStoreTool initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize MemoryStoreTool: {e}")
        else:
            if self.debug:
                logger.info("MemoryStoreTool disabled in configuration")

        # Initialize sentiment analyzer tool
        if "sentiment" in enabled_tools:
            try:
                tool_config = enabled_tools["sentiment"]
                sentiment_config = tool_config.config
                tools["sentiment"] = SentimentAnalyzerTool(sentiment_config)
                if self.debug:
                    logger.info("SentimentAnalyzerTool initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize SentimentAnalyzerTool: {e}")
        else:
            if self.debug:
                logger.info("SentimentAnalyzerTool disabled in configuration")

        # Initialize code executor tool
        if "code_execution" in enabled_tools:
            try:
                tool_config = enabled_tools["code_execution"]
                code_exec_config = {
                    "timeout_seconds": tool_config.config.get("timeout_seconds", 30),
                    "memory_limit": str(tool_config.config.get("memory_limit_mb", 128)) + "m",
                    "cpu_quota": 100000,
                    "image": tool_config.config.get("sandbox_image", "kai-python-sandbox:latest"),
                    "use_gvisor": tool_config.config.get("runtime", "").lower() == "gvisor",
                    "network_disabled": True,
                }
                # Use wrapper that supports auto-generation
                tools["code_exec"] = CodeExecWrapper(code_exec_config)
                if self.debug:
                    logger.info("CodeExecWrapper initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize CodeExecWrapper: {e}")
        else:
            if self.debug:
                logger.info("CodeExecWrapper disabled in configuration")

        # Add stub tools as fallback if real tools failed to initialize
        if "web_search" not in tools:
            logger.warning("WebSearchTool not available, adding stub")
            from src.tools.base_tool import BaseTool, ToolResult, ToolStatus

            class StubWebSearch(BaseTool):
                async def execute(self, parameters):
                    return ToolResult(
                        tool_name="web_search",
                        status=ToolStatus.FAILED,
                        error="Web search dependencies not installed (duckduckgo-search)",
                        data={"query": parameters.get("query", "")},
                    )

                async def fallback(self, parameters, error):
                    return await self.execute(parameters)

            tools["web_search"] = StubWebSearch({"enabled": True})

        if "code_exec" not in tools:
            logger.warning("CodeExecWrapper not available, adding stub")
            from src.tools.base_tool import BaseTool, ToolResult, ToolStatus

            class StubCodeExec(BaseTool):
                async def execute(self, parameters):
                    return ToolResult(
                        tool_name="code_exec",
                        status=ToolStatus.FAILED,
                        error="Code execution dependencies not installed (docker)",
                        data={
                            "task": parameters.get("task", ""),
                            "code": parameters.get("code", ""),
                        },
                    )

                async def fallback(self, parameters, error):
                    return await self.execute(parameters)

            tools["code_exec"] = StubCodeExec({"enabled": True})

        if self.debug:
            logger.info(f"Initialized {len(tools)} tools: {list(tools.keys())}")

        return tools

    async def start_conversation(self):
        """Start a new conversation."""
        cost_limit = self.config.get_env("default_cost_limit")
        self.conversation = self.conversation_service.create_conversation(
            user_id=self.user_id, cost_limit=cost_limit, source="cli"
        )
        logger.info(f"Started conversation {self.conversation.session_id}")

    async def chat_loop(self):
        """Main interactive chat loop."""
        print("\nKai LLM Orchestrator")
        print("=" * 50)
        print("Type 'quit' or 'exit' to end conversation")
        print("Type '/cost' to check spending")
        print("React: 😭 (too long) 🤓 (nerdy) 💀 (bad tone)")
        print("Commands: /regen, 'never', /reset")
        print("=" * 50)
        print()

        # Start conversation
        await self.start_conversation()

        while True:
            try:
                # Get user input
                user_input = input("🗨️ You: ").strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.lower() in ["quit", "exit", "bye"]:
                    print("\n👋 Goodbye!")
                    break

                if user_input.lower() == "/cost":
                    self._show_cost()
                    continue

                # Rage feedback reactions
                if user_input in ["😭", "🤓", "💀"]:
                    response_msg = await self.rage_trainer.record_reaction(user_input)
                    print(f"\n💬 Kai: {response_msg}\n")
                    continue

                # Regen command
                if user_input.lower() == "/regen":
                    regen_ctx = await self.rage_trainer.handle_regen(force_external=False)
                    if "error" in regen_ctx:
                        print(f"\n⚠️  {regen_ctx['error']}\n")
                        continue
                    # Regenerate with anti-pattern context
                    print("\n🔄 Regenerating...\n")
                    user_input = f"{regen_ctx['instruction']}\n\nApply these rules:\n{regen_ctx['apply_rules']}"
                    # Continue to normal processing

                # Never command
                if user_input.lower() == "never":
                    print("\n💬 Kai: never do what again?\n")
                    what = input("🗨️ You: ").strip()
                    if what:
                        response_msg = await self.rage_trainer.handle_never_command(what)
                        print(f"\n💬 Kai: {response_msg}\n")
                    continue

                # Weekly summary command
                if user_input.lower() == "/summary":
                    summary = self.rage_trainer.get_weekly_summary()
                    msg = format_weekly_message(summary)
                    print(f"\n💬 Kai: {msg}\n")
                    continue

                # Nuclear reset command
                if user_input.lower() == "/reset":
                    confirm = input("⚠️  This will delete all learned preferences. Type 'yes' to confirm: ")
                    if confirm.lower() == "yes":
                        response_msg = await self.rage_trainer.nuclear_reset()
                        print(f"\n💬 Kai: {response_msg}\n")
                    else:
                        print("\nCancelled.\n")
                    continue

                # Memory commands
                if user_input.startswith("/mem") or user_input.startswith("/memory"):
                    self._handle_memory_command(user_input)
                    continue

                # Add newline after user input for clean separation
                print()

                # Process query with streaming
                print("💭 Thinking...", end="", flush=True)

                # Collect streamed content with natural pacing
                full_content = []
                print("\r" + " " * 20 + "\r", end="")  # Clear thinking message
                print("💬 Kai: ", end="", flush=True)

                # Stream with natural reading rhythm
                char_count = 0
                async for chunk in self.orchestrator.process_query_stream(
                    query_text=user_input,
                    conversation=self.conversation,
                    source="cli",
                ):
                    for char in chunk:
                        print(char, end="", flush=True)
                        full_content.append(char)
                        
                        # Natural pauses for better reading rhythm
                        if char in '.!?':
                            await asyncio.sleep(0.08)  # Sentence pause
                        elif char in ',;:':
                            await asyncio.sleep(0.04)  # Clause pause
                        elif char == '\n':
                            await asyncio.sleep(0.06)  # Paragraph pause
                        else:
                            # Very subtle base delay with variation for natural feel
                            base_delay = 0.012
                            variation = 0.003 * ((char_count % 5) / 5 - 0.5)
                            await asyncio.sleep(max(0.008, base_delay + variation))
                        
                        char_count += 1

                print()  # Newline after streaming complete

                # Capture response for rage feedback
                full_response_text = "".join(full_content)
                self.rage_trainer.capture_response(full_response_text)

                # Create response object from streamed content
                from src.models.response import Response
                response = Response(
                    query_id=str(uuid.uuid4()),
                    mode="concise",
                    content="".join(full_content),
                    token_count=0,
                    cost=0.0,
                )

                # Save messages to database
                query_data = {
                    "message_id": str(uuid.uuid4()),
                    "session_id": self.conversation.session_id,
                    "role": "user",
                    "content": user_input,
                }
                self.conversation_service.save_message(query_data)

                response_dict = response.to_dict()
                response_dict["session_id"] = self.conversation.session_id
                self.conversation_service.save_message(response_dict)

                # Update conversation cost
                self.conversation_service.update_cost(
                    self.conversation.session_id,
                    response.cost,
                )

                # Log episodic memory and reflection in background (non-blocking)
                # This runs asynchronously so the next prompt appears immediately
                asyncio.create_task(
                    self._process_memory_and_reflection(
                        user_input=user_input,
                        response=response,
                    )
                )

                # Response already displayed during streaming
                # Display additional metadata

                # Display code execution results if present
                if hasattr(response, 'tool_results') and response.tool_results:
                    code_results = [t for t in response.tool_results if t.tool_name == "code_exec"]
                    if code_results:
                        print("\n🔬 Code Execution:")
                        for result in code_results:
                            stdout = result.data.get("stdout", "")
                            stderr = result.data.get("stderr", "")
                            exit_code = result.data.get("exit_code", -1)

                            if stdout:
                                print(f"   Output: {stdout}")
                            if stderr:
                                print(f"   Errors: {stderr}")
                            if exit_code != 0:
                                print(f"   Exit Code: {exit_code}")

                # Display citations if present
                if hasattr(response, 'has_citations') and response.has_citations():
                    print("\n📚 Sources:")
                    for i, citation in enumerate(response.source_citations[:3], 1):
                        print(f"   {i}. {citation.title}")
                        print(f"      {citation.url}")

                # Check cost warnings from orchestrator cost tracker
                cost_summary = self.orchestrator.get_cost_summary(self.conversation.session_id)

                if cost_summary["soft_cap_reached"]:
                    print(
                        f"\n⚠️  Soft cap reached! "
                        f"(${cost_summary['total_cost']:.4f}/"
                        f"${cost_summary['limit']:.2f}) "
                        f"- Using local models to save costs"
                    )
                elif cost_summary["hard_cap_reached"]:
                    print(
                        f"\n🛑 Hard cap reached! "
                        f"(${cost_summary['total_cost']:.4f}/"
                        f"${cost_summary['limit']:.2f}) "
                        f"- Only local models available"
                    )
                elif self.conversation.approaching_limit():
                    remaining_pct = (cost_summary["remaining"] / cost_summary["limit"]) * 100
                    print(
                        f"\n⚠️  Approaching cost limit: "
                        f"${cost_summary['total_cost']:.4f}/"
                        f"${cost_summary['limit']:.2f} "
                        f"({remaining_pct:.0f}% remaining)"
                    )

                # Add blank line before next prompt
                print()

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break

            except Exception as e:
                logger.error(f"Error processing query: {e}", exc_info=True)
                print(f"\n❌ Error: {e}")
                print("Please try again or type 'quit' to exit.\n")

        # End conversation
        if self.conversation:
            self.conversation_service.end_conversation(self.conversation.session_id)
            logger.info("Conversation ended")

    async def _process_memory_and_reflection(
        self,
        user_input: str,
        response,
    ):
        """Process episodic memory and reflection in background.

        This runs asynchronously after response is displayed,
        avoiding blocking the next user prompt.

        Args:
            user_input: User's query text
            response: Response object from orchestrator
        """
        # Log episodic memory to file vault
        episode_record = None
        try:
            episode_record = self.memory_vault.add_episode(
                session_id=self.conversation.session_id,
                user_text=user_input,
                assistant_text=response.content,
                success=True,
                summary=response.format_content()[:200],
                confidence=min(max(response.confidence, 0.0), 1.0)
                if hasattr(response, "confidence")
                else None,
                tags=[response.mode] if hasattr(response, "mode") else [],
            )
        except Exception as e:
            logger.warning(f"Failed to write episodic memory: {e}")

        # Generate reflection (always runs in background for continuous learning)
        if self.reflection_agent and episode_record:
            try:
                if self.show_reflection:
                    print("\n🔮 Reflecting on this interaction...")

                tools_used = (
                    [t.tool_name for t in response.tool_results]
                    if hasattr(response, "tool_results") and response.tool_results
                    else []
                )
                await self.reflection_agent.reflect_on_episode(
                    episode_id=episode_record.id,
                    user_text=user_input,
                    assistant_text=response.content,
                    success=True,
                    mode=response.mode,
                    tools_used=tools_used,
                )

                if self.show_reflection:
                    print("✓ Reflection complete - learning stored\n")
                elif self.debug:
                    logger.debug(f"Generated reflection for episode {episode_record.id}")
            except Exception as e:
                if self.show_reflection:
                    print(f"⚠️  Reflection failed: {e}\n")
                logger.warning(f"Failed to generate reflection: {e}")

    def _show_cost(self):
        """Display current conversation cost."""
        cost_summary = self.orchestrator.get_cost_summary(self.conversation.session_id)

        print("\n💰 Cost Summary:")
        print(f"   Session Cost: ${cost_summary['total_cost']:.4f} / ${cost_summary['limit']:.2f}")
        print(f"   Queries: {cost_summary['query_count']}")
        print(f"   Remaining: ${cost_summary['remaining']:.4f}")

        if cost_summary["soft_cap_reached"]:
            print("   Status: ⚠️  Soft cap reached - using cheaper models")
        elif cost_summary["hard_cap_reached"]:
            print("   Status: 🛑 Hard cap reached - local models only")
        else:
            pct_used = (cost_summary["total_cost"] / cost_summary["limit"]) * 100
            print(f"   Status: ✓ {pct_used:.0f}% of budget used")

        print()

    async def run(self):
        """Run the CLI application."""
        try:
            # Check health of connectors
            print("Checking model availability...")
            health = await self.orchestrator.check_health()

            if not health.get("local_model", False):
                print("❌ Error: Local model (Ollama) is not available.")
                print("Please ensure Ollama is running: ollama serve")
                return

            print("✅ Local model ready")

            # Start chat loop
            await self.chat_loop()

        except Exception as e:
            logger.error(f"CLI error: {e}", exc_info=True)
            print(f"\n❌ Fatal error: {e}")

        finally:
            # Cleanup
            if hasattr(self.local_connector, "close"):
                await self.local_connector.close()

    def _handle_memory_command(self, cmd: str):
        """Handle /mem commands.

        Commands:
          /mem list [type]
          /mem export [path]
          /mem prune
        """
        parts = cmd.strip().split()
        if len(parts) == 1 or parts[1] in {"help", "-h", "--help"}:
            print(
                "\n🧠 Memory Vault Commands:\n  /mem list [type]     - Show recent memories (all or by type)\n  /mem export [path]   - Export all memories to Markdown file\n  /mem prune           - Remove expired/low-confidence memories\n  Types: episodic, semantic, preference, bug_fix, reflection, prompt, checklist\n"
            )
            return

        action = parts[1]
        if action == "list":
            mtype = parts[2] if len(parts) > 2 else None
            recs = self.memory_vault.list(mtype=mtype, limit=20)
            print(f"\n🧠 {len(recs)} memories" + (f" (type={mtype})" if mtype else "") + ":")
            for r in recs:
                print(
                    f"  - [{r.get('type')}] {r.get('id')} | {r.get('created_at')} | {r.get('summary') or '(no summary)'}"
                )
            print()
            return
        if action == "export":
            out = parts[2] if len(parts) > 2 else f"data/memory/{self.user_id}/export.md"
            path = self.memory_vault.export_markdown(out)
            print(f"\n✅ Exported to {path}\n")
            return
        if action == "prune":
            stats = self.memory_vault.prune()
            total = sum(stats.values())
            print(
                f"\n🧹 Pruned {total} memories: "
                + ", ".join([f"{k}={v}" for k, v in stats.items() if v])
            )
            print()
            return
        print("\n❓ Unknown memory command. Try /mem help\n")

    async def import_chatgpt(self, file_path: str):
        """Import ChatGPT history from file."""
        if not self.local_connector:
            print("❌ Error: Local model (Ollama) is required for import analysis.")
            return

        print(f"\n🚀 Starting ChatGPT Import from {file_path}")
        print("This will parse conversations and extract memories/preferences...")
        
        importer = ChatGPTImporter(self.memory_vault, self.local_connector)
        stats = await importer.import_file(file_path)
        
        if "error" in stats:
            print(f"\n❌ Import failed: {stats['error']}")
        else:
            print(f"\n✅ Import Complete!")
            print(f"   - Conversations: {stats['conversations']}")
            print(f"   - Episodes: {stats['episodes']}")
            print(f"   - Semantic Memories: {stats['semantic']}")
            print(f"   - Preferences: {stats['preferences']}")
            print(f"   - Rules: {stats['rules']}")
            print(f"\nKai now remembers {stats['conversations']} conversations of your chaos.")


async def main(debug: bool = False, show_reflection: bool = False, import_chatgpt: str | None = None):
    """Main entry point.

    Args:
        debug: Enable debug mode with verbose logging
        show_reflection: Show detailed reflection output (reflection always runs in background)
        import_chatgpt: Path to ChatGPT export file to import
    """
    cli = CLI(debug=debug, show_reflection=show_reflection)
    
    if import_chatgpt:
        await cli.import_chatgpt(import_chatgpt)
        return

    await cli.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Kai - Intelligent LLM Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  ./kai                   # Clean output (default)
  ./kai --debug          # Verbose logging for debugging
        """,
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode with verbose logging"
    )
    parser.add_argument(
        "--reflect",
        action="store_true",
        help="Show detailed reflection process (reflection always runs in background)",
    )
    parser.add_argument(
        "--import-chatgpt",
        type=str,
        help="Import ChatGPT history from conversations.json",
    )

    args = parser.parse_args()
    asyncio.run(main(debug=args.debug, show_reflection=args.reflect, import_chatgpt=args.import_chatgpt))
