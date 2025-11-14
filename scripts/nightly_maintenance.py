#!/usr/bin/env python3
"""Nightly maintenance script for memory management and distillation.

Run this script daily (e.g., via cron) to:
1. Run distillation sweeps on recent memories
2. Prune expired/low-confidence memories
3. Generate reports on system improvements

Usage:
    python scripts/nightly_maintenance.py [--user-id USER_ID] [--days 7]
"""

import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.memory_vault import MemoryVault
from src.agents.reflection_agent import ReflectionAgent
from src.core.providers.ollama_provider import OllamaProvider
from src.lib.logger import setup_logging

logger = logging.getLogger(__name__)


async def run_maintenance(user_id: str, days: int = 7):
    """Run nightly maintenance tasks.
    
    Args:
        user_id: User ID to process
        days: Days of history to analyze
    """
    print(f"\n{'='*60}")
    print(f"Kai Nightly Maintenance - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")
    
    # Initialize memory vault
    vault = MemoryVault(user_id=user_id)
    
    # Initialize reflection agent with local LLM
    llm_config = {
        "model_id": "granite-local",
        "model_name": "granite4:tiny-h",
        "provider": "ollama",
        "capabilities": [],
        "context_window": 4096,
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
    }
    
    try:
        llm = OllamaProvider(llm_config, "http://localhost:11434")
        reflection_agent = ReflectionAgent(llm, vault)
        
        # 1. Run distillation sweep
        print("📊 Running distillation sweep...")
        sweep_result = await reflection_agent.distillation_sweep(
            days_back=days,
            min_episodes=5,
        )
        
        if sweep_result["status"] == "completed":
            distilled = sweep_result.get("distilled", {})
            print(f"✅ Distillation completed:")
            print(f"   - Analyzed {sweep_result['episodes_analyzed']} episodes")
            print(f"   - Analyzed {sweep_result['reflections_analyzed']} reflections")
            print(f"   - Generated {len(distilled.get('rules', []))} new rules")
            print(f"   - Generated {len(distilled.get('prompts', []))} prompt patterns")
            print(f"   - Generated {len(distilled.get('procedures', []))} procedures")
        elif sweep_result["status"] == "skipped":
            print(f"⏭️  Distillation skipped: {sweep_result.get('reason', 'unknown')}")
        else:
            print(f"❌ Distillation failed: {sweep_result.get('error', 'unknown')}")
        
        print()
        
        # 2. Prune old/low-confidence memories
        print("🧹 Pruning expired memories...")
        prune_stats = vault.prune()
        total_pruned = sum(prune_stats.values())
        
        if total_pruned > 0:
            print(f"✅ Pruned {total_pruned} memories:")
            for mtype, count in prune_stats.items():
                if count > 0:
                    print(f"   - {mtype}: {count}")
        else:
            print("   No memories to prune")
        
        print()
        
        # 3. Generate summary report
        print("📝 Memory summary:")
        all_memories = vault.list()
        by_type = {}
        for m in all_memories:
            mtype = m.get("type", "unknown")
            by_type[mtype] = by_type.get(mtype, 0) + 1
        
        for mtype, count in sorted(by_type.items()):
            print(f"   - {mtype}: {count}")
        
        print(f"\n   Total: {len(all_memories)} memories")
        
        # 4. Export current state
        export_path = f"data/memory/{user_id}/maintenance_export_{datetime.now().strftime('%Y%m%d')}.md"
        vault.export_markdown(export_path)
        print(f"\n💾 Exported to: {export_path}")
        
        print(f"\n{'='*60}")
        print("✅ Maintenance completed successfully")
        print(f"{'='*60}\n")
        
    except Exception as e:
        logger.error(f"Maintenance failed: {e}", exc_info=True)
        print(f"\n❌ Maintenance failed: {e}\n")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Nightly maintenance for Kai memory system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--user-id",
        default="default",
        help="User ID to process (default: 'default')",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Days of history to analyze (default: 7)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(
        log_level="DEBUG" if args.debug else "INFO",
        structured=False,
        quiet=not args.debug,
    )
    
    # Run maintenance
    asyncio.run(run_maintenance(args.user_id, args.days))


if __name__ == "__main__":
    main()
