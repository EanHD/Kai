#!/usr/bin/env python3
"""Weekly rage training report - sends summary every Sunday 9am.

Run via cron:
    0 9 * * 0 cd /path/to/kai && python scripts/weekly_rage_report.py
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.memory_vault import MemoryVault
from src.feedback.rage_trainer import RageTrainer, format_weekly_message


async def send_weekly_report(user_id: str = "default"):
    """Generate and display weekly rage report."""
    print(f"\n{'='*60}")
    print(f"Weekly Rage Training Report - {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*60}\n")

    # Initialize vault and trainer
    vault = MemoryVault(user_id=user_id)
    trainer = RageTrainer(vault)

    # Get summary
    summary = trainer.get_weekly_summary()
    message = format_weekly_message(summary)

    print(f"📊 {message}\n")
    print(f"{'='*60}\n")

    # In production, this would send via notification/email
    # For now, just print to console


if __name__ == "__main__":
    user_id = sys.argv[1] if len(sys.argv) > 1 else "default"
    asyncio.run(send_weekly_report(user_id))
