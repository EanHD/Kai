"""Reflection Agent for self-improvement through learning from past interactions.

This agent:
1. Analyzes completed episodes to extract learnings
2. Distills patterns into actionable knowledge
3. Generates new rules, prompts, and checklists
4. Stores reflections for future reference
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, UTC, timedelta
from typing import Any

from src.core.llm_connector import Message
from src.storage.memory_vault import MemoryVault

logger = logging.getLogger(__name__)


@dataclass
class ReflectionPrompt:
    """Prompts for the reflection agent to analyze episodes."""

    EPISODE_REFLECTION = """Analyze this conversation episode and extract key learnings.

Episode:
User: {user_text}
Assistant: {assistant_text}
Success: {success}
Mode: {mode}

Provide:
1. What went well?
2. What could be improved?
3. Any patterns or rules we should remember?
4. Suggested prompt improvements?

Be concise and actionable."""

    DISTILLATION_SWEEP = """Analyze these {count} recent episodes and reflections to distill key learnings.

Recent patterns:
{summaries}

Generate:
1. New rules learned (if any)
2. Common failure patterns (if any)
3. Successful prompt patterns (if any)
4. Procedural steps to add to checklists (if any)

Format as JSON with keys: rules, failures, prompts, procedures"""


class ReflectionAgent:
    """Agent that learns from past interactions to improve future performance."""

    def __init__(self, llm_connector, memory_vault: MemoryVault):
        """Initialize reflection agent.

        Args:
            llm_connector: LLM connector for generating reflections
            memory_vault: Memory vault for storing/retrieving memories
        """
        self.llm = llm_connector
        self.vault = memory_vault

    async def reflect_on_episode(
        self,
        episode_id: str,
        user_text: str,
        assistant_text: str,
        success: bool | None = None,
        mode: str = "concise",
        tools_used: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Generate reflection on a single episode.

        Args:
            episode_id: Episode memory ID
            user_text: User's input
            assistant_text: Assistant's response
            success: Whether the interaction was successful
            mode: Response mode used
            tools_used: List of tools invoked

        Returns:
            Reflection data dict or None if reflection fails
        """
        try:
            # Build reflection prompt
            prompt_text = ReflectionPrompt.EPISODE_REFLECTION.format(
                user_text=user_text[:500],  # Truncate for context
                assistant_text=assistant_text[:500],
                success=success if success is not None else "unknown",
                mode=mode,
            )

            # Generate reflection using LLM
            messages = [Message(role="user", content=prompt_text)]
            response = await self.llm.generate(messages, temperature=0.3, max_tokens=300)

            reflection_text = response.content.strip()

            # Parse basic structure (simple heuristic)
            learnings = self._extract_learnings(reflection_text)

            # Store reflection
            reflection = self.vault.add(
                "reflection",
                payload={
                    "episode_id": episode_id,
                    "user_text": user_text[:200],
                    "assistant_text": assistant_text[:200],
                    "success": success,
                    "mode": mode,
                    "tools_used": tools_used or [],
                    "reflection": reflection_text,
                    "learnings": learnings,
                },
                summary=f"Reflection on {mode} response",
                confidence=0.7,
                ttl_days=180,  # Keep reflections longer than episodes
                tags=["auto-generated", mode] + (tools_used or []),
            )

            logger.info(f"Generated reflection for episode {episode_id}")
            return reflection.to_dict()

        except Exception as e:
            logger.error(f"Failed to generate reflection: {e}")
            return None

    def _extract_learnings(self, reflection_text: str) -> dict[str, list[str]]:
        """Extract structured learnings from reflection text.

        Simple heuristic parser - looks for numbered lists and bullet points.
        """
        learnings = {
            "what_went_well": [],
            "improvements": [],
            "rules": [],
            "prompt_suggestions": [],
        }

        lines = reflection_text.split("\n")
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect sections
            if "went well" in line.lower():
                current_section = "what_went_well"
            elif "improve" in line.lower():
                current_section = "improvements"
            elif "rule" in line.lower() or "pattern" in line.lower():
                current_section = "rules"
            elif "prompt" in line.lower():
                current_section = "prompt_suggestions"

            # Extract bullet points or numbered items
            if current_section and (
                line.startswith("-")
                or line.startswith("•")
                or (len(line) > 2 and line[0].isdigit() and line[1] in ".)")
            ):
                content = line.lstrip("-•0123456789.) ").strip()
                if content:
                    learnings[current_section].append(content)

        return learnings

    async def distillation_sweep(
        self,
        days_back: int = 7,
        min_episodes: int = 5,
    ) -> dict[str, Any]:
        """Run distillation sweep to extract high-level patterns.

        Analyzes recent episodes and reflections to generate:
        - New semantic rules
        - Updated prompt templates
        - Procedural checklists

        Args:
            days_back: How many days to analyze
            min_episodes: Minimum episodes needed to run sweep

        Returns:
            Summary of distilled knowledge
        """
        try:
            # Get recent episodes and reflections
            cutoff = datetime.now(UTC) - timedelta(days=days_back)

            episodes = [
                e
                for e in self.vault.list(mtype="episodic", limit=100)
                if datetime.fromisoformat(e["created_at"]) > cutoff
            ]

            reflections = [
                r
                for r in self.vault.list(mtype="reflection", limit=100)
                if datetime.fromisoformat(r["created_at"]) > cutoff
            ]

            if len(episodes) < min_episodes:
                logger.info(f"Not enough episodes ({len(episodes)}) for distillation sweep")
                return {"status": "skipped", "reason": "insufficient_data"}

            # Build summary of recent patterns
            summaries = []
            for refl in reflections[:20]:  # Limit for context
                payload = refl.get("payload", {})
                summary = refl.get("summary", "")
                learnings = payload.get("learnings", {})

                if learnings.get("rules"):
                    summaries.append(f"Rules: {', '.join(learnings['rules'][:2])}")
                if summary:
                    summaries.append(f"- {summary}")

            summary_text = "\n".join(summaries) if summaries else "No significant patterns"

            # Generate distillation using LLM
            prompt_text = ReflectionPrompt.DISTILLATION_SWEEP.format(
                count=len(episodes),
                summaries=summary_text[:1000],  # Truncate
            )

            messages = [Message(role="user", content=prompt_text)]
            response = await self.llm.generate(messages, temperature=0.3, max_tokens=500)

            distilled = self._parse_distillation(response.content)

            # Store distilled knowledge as semantic memories
            if distilled.get("rules"):
                for rule_item in distilled["rules"][:5]:  # Top 5
                    # Handle both string and dict formats
                    if isinstance(rule_item, dict):
                        rule_text = rule_item.get("rule", str(rule_item))
                    else:
                        rule_text = str(rule_item)

                    self.vault.add(
                        "semantic",
                        payload={"rule": rule_text, "source": "distillation"},
                        summary=f"Rule: {rule_text[:100]}",
                        confidence=0.8,
                        tags=["rule", "distilled"],
                    )

            # Store prompt improvements
            if distilled.get("prompts"):
                for prompt_item in distilled["prompts"][:3]:
                    # Handle both string and dict formats
                    if isinstance(prompt_item, dict):
                        prompt_text = prompt_item.get(
                            "prompt", prompt_item.get("pattern", str(prompt_item))
                        )
                    else:
                        prompt_text = str(prompt_item)

                    self.vault.add(
                        "prompt",
                        payload={"pattern": prompt_text, "source": "distillation"},
                        summary=f"Prompt pattern: {prompt_text[:100]}",
                        confidence=0.7,
                        tags=["prompt", "distilled"],
                    )

            # Store procedural steps
            if distilled.get("procedures"):
                for proc_item in distilled["procedures"][:3]:
                    # Handle both string and dict formats
                    if isinstance(proc_item, dict):
                        proc_text = proc_item.get(
                            "procedure", proc_item.get("step", str(proc_item))
                        )
                    else:
                        proc_text = str(proc_item)

                    self.vault.add(
                        "checklist",
                        payload={"step": proc_text, "source": "distillation"},
                        summary=f"Procedure: {proc_text[:100]}",
                        confidence=0.7,
                        tags=["procedure", "distilled"],
                    )

            logger.info(
                f"Distillation sweep completed: {len(distilled.get('rules', []))} rules, "
                f"{len(distilled.get('prompts', []))} prompts, "
                f"{len(distilled.get('procedures', []))} procedures"
            )

            return {
                "status": "completed",
                "episodes_analyzed": len(episodes),
                "reflections_analyzed": len(reflections),
                "distilled": distilled,
            }

        except Exception as e:
            logger.error(f"Distillation sweep failed: {e}")
            return {"status": "failed", "error": str(e)}

    def _parse_distillation(self, text: str) -> dict[str, list[str]]:
        """Parse distillation output into structured format.

        Looks for JSON or falls back to heuristic parsing.
        """
        import json

        # Try JSON first
        try:
            # Find JSON block
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                json_text = text[start : end + 1]
                parsed = json.loads(json_text)
                return {
                    "rules": parsed.get("rules", []),
                    "failures": parsed.get("failures", []),
                    "prompts": parsed.get("prompts", []),
                    "procedures": parsed.get("procedures", []),
                }
        except Exception:
            pass

        # Fallback: heuristic parsing
        result = {"rules": [], "failures": [], "prompts": [], "procedures": []}

        lines = text.split("\n")
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect sections
            if "rule" in line.lower():
                current_section = "rules"
            elif "fail" in line.lower():
                current_section = "failures"
            elif "prompt" in line.lower():
                current_section = "prompts"
            elif "procedure" in line.lower() or "step" in line.lower():
                current_section = "procedures"

            # Extract items
            if current_section and (
                line.startswith("-")
                or line.startswith("•")
                or (len(line) > 2 and line[0].isdigit() and line[1] in ".)")
            ):
                content = line.lstrip("-•0123456789.) ").strip()
                if content:
                    result[current_section].append(content)

        return result
