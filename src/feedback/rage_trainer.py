"""Rage Training Feedback System - Learn from every eye-roll instantly."""

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from src.storage.memory_vault import MemoryVault

logger = logging.getLogger(__name__)


class RageTrainer:
    """Captures user frustration and converts it to permanent behavioral change."""

    REACTIONS = {
        "😭": "too_long",
        "🤓": "over_explaining",
        "💀": "tone_wrong",
    }

    def __init__(self, memory_vault: MemoryVault):
        self.vault = memory_vault
        self.last_response = None
        self.last_response_time = None
        self.pending_regen = False

    def capture_response(self, response_text: str):
        """Store last response for potential feedback."""
        self.last_response = response_text
        self.last_response_time = datetime.now(UTC)

    async def record_reaction(self, emoji: str, context: str = "") -> str:
        """Record a negative reaction and create permanent rule.

        Args:
            emoji: One of 😭🤓💀
            context: Optional context about what was wrong

        Returns:
            Confirmation message
        """
        if emoji not in self.REACTIONS:
            return ""

        reaction_type = self.REACTIONS[emoji]
        offending_message = self.last_response or context

        # Create permanent rule with high weight
        rule_text = self._generate_rule(reaction_type, offending_message[:500])

        self.vault.add(
            "checklist",
            payload={
                "rule": rule_text,
                "source": "rage_training",
                "reaction_type": reaction_type,
                "offending_text": offending_message[:200],
                "distillation_weight": 10,  # 10× weight for rage feedback
            },
            summary=f"Rage feedback ({emoji}): {rule_text[:100]}",
            confidence=1.0,
            ttl_days=None,  # Never expires
            tags=["rage_training", reaction_type, "permanent"],
        )

        logger.info(f"Rage feedback recorded: {emoji} → {rule_text}")
        return f"got it. never doing that again. ({emoji})"

    def _generate_rule(self, reaction_type: str, offending_text: str) -> str:
        """Generate rule text from reaction type."""
        rules = {
            "too_long": f"NEVER be verbose like this again: '{offending_text[:100]}...' — user wants SHORT answers",
            "over_explaining": f"STOP over-explaining. User hated this nerdy response: '{offending_text[:100]}...' — be concise",
            "tone_wrong": f"WRONG TONE. User rejected: '{offending_text[:100]}...' — match their energy, don't be cringe",
        }
        return rules.get(reaction_type, f"User rejected: {offending_text[:100]}")

    async def handle_regen(self, force_external: bool = False) -> dict[str, Any]:
        """Handle regeneration request.

        Args:
            force_external: If True, escalate to external model

        Returns:
            Dict with regen context
        """
        if not self.last_response:
            return {"error": "No previous response to regenerate"}

        # Get all rage rules
        rage_rules = self.vault.list(mtype="checklist", tag="rage_training")
        rules_text = "\n".join(
            [
                f"- {r.get('payload', {}).get('rule', '')}"
                for r in rage_rules[-10:]  # Last 10 rules
            ]
        )

        return {
            "instruction": "USER HATED THE LAST ONE — DO NOT REPEAT",
            "rejected_response": self.last_response[:500],
            "apply_rules": rules_text,
            "force_external": force_external,
        }

    async def handle_never_command(self, what_to_never_do: str) -> str:
        """Handle 'never' command - creates permanent rule.

        Args:
            what_to_never_do: What user wants Kai to never do

        Returns:
            Confirmation message
        """
        rule_text = f"NEVER {what_to_never_do}"

        self.vault.add(
            "checklist",
            payload={
                "rule": rule_text,
                "source": "never_command",
                "distillation_weight": 10,
            },
            summary=f"Never command: {rule_text[:100]}",
            confidence=1.0,
            ttl_days=None,
            tags=["never_command", "permanent"],
        )

        logger.info(f"Never command recorded: {rule_text}")
        return f"understood. i will never {what_to_never_do} again."

    def get_weekly_summary(self) -> dict[str, Any]:
        """Generate weekly rage summary.

        Returns:
            Dict with weekly stats
        """
        week_ago = datetime.now(UTC) - timedelta(days=7)

        # Get rage feedback from last week
        all_rage = self.vault.list(mtype="checklist", tag="rage_training")
        weekly_rage = [
            r
            for r in all_rage
            if datetime.fromisoformat(r.get("created_at", "")) > week_ago
        ]

        if not weekly_rage:
            return {"message": "no rage this week. you must be tolerating my bullshit."}

        # Count reactions by type
        reaction_counts = {}
        for r in weekly_rage:
            rtype = r.get("payload", {}).get("reaction_type", "unknown")
            reaction_counts[rtype] = reaction_counts.get(rtype, 0) + 1

        # Find top rage
        top_rage = max(reaction_counts.items(), key=lambda x: x[1], default=("none", 0))
        emoji_map = {v: k for k, v in self.REACTIONS.items()}
        top_emoji = emoji_map.get(top_rage[0], "🤷")

        # Get worst offense
        worst = weekly_rage[-1]  # Most recent
        worst_text = worst.get("payload", {}).get("offending_text", "nothing specific")

        return {
            "new_learnings": len(weekly_rage),
            "top_rage_type": top_rage[0],
            "top_rage_emoji": top_emoji,
            "top_rage_count": top_rage[1],
            "worst_offense": worst_text[:150],
        }

    async def nuclear_reset(self) -> str:
        """Wipe all learned preferences and rules, reset to baseline.

        Returns:
            Confirmation message
        """
        # Delete all distilled preferences, rules, prompts
        deleted_count = 0

        for mtype in ["preference", "checklist", "prompt", "semantic"]:
            path = self.vault._path_for_type(mtype)
            if not path.exists():
                continue

            # Filter out learned content, keep only system defaults
            kept_lines = []
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                        source = obj.get("payload", {}).get("source", "")

                        # Keep only non-learned content
                        if source not in [
                            "distillation",
                            "rage_training",
                            "never_command",
                            "chatgpt_import",
                        ]:
                            kept_lines.append(line)
                        else:
                            deleted_count += 1
                    except Exception:
                        kept_lines.append(line)  # Keep malformed entries

            # Rewrite file
            with path.open("w", encoding="utf-8") as f:
                f.writelines(kept_lines)

        logger.warning(f"Nuclear reset: deleted {deleted_count} learned behaviors")
        return f"reset complete. deleted {deleted_count} learned behaviors. back to baseline."


def format_weekly_message(summary: dict[str, Any]) -> str:
    """Format weekly summary as user message."""
    if "message" in summary:
        return summary["message"]

    return (
        f"this week i permanently learned {summary['new_learnings']} things about you. "
        f"top rage: {summary['top_rage_emoji']} ({summary['top_rage_count']} times). "
        f"worst offense i'll never repeat again: \"{summary['worst_offense']}\""
    )
