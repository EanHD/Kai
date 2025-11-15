#!/bin/bash
# Quick validation script to check system readiness

echo "🔍 KAI Quick Validation"
echo "======================="
echo

# Test import
echo "✓ Testing imports..."
python3 -c "from src.core.orchestrator import Orchestrator; from src.api.adapter import APIAdapter" && echo "  ✅ Core modules OK" || echo "  ❌ Import failed"

# Test calculation
echo "✓ Testing calculation accuracy..."
python3 <<EOF
import asyncio
from src.tools.code_exec_wrapper import CodeExecWrapper

async def test():
    wrapper = CodeExecWrapper({'enabled': True})
    result = await wrapper.execute({
        'language': 'python',
        'mode': 'task',
        'task': 'battery_pack_energy',
        'variables': {
            'cells_in_series': 14,
            'cells_in_parallel': 5,
            'cell_nominal_voltage_v': 3.6,
            'cell_nominal_capacity_ah': 5.0
        }
    })
    energy = result.data.get('pack_energy_kwh', 0)
    expected = 1.26
    if abs(energy - expected) < 0.01:
        print(f"  ✅ Calculation OK: 14S5P = {energy:.3f} kWh")
        return True
    else:
        print(f"  ❌ Wrong: got {energy}, expected {expected}")
        return False

asyncio.run(test())
EOF

# Count tests
echo "✓ Counting tests..."
TOTAL=$(find tests/ -name "test_*.py" -type f | xargs grep -h "^def test_\|^    async def test_" | wc -l)
echo "  ℹ️  Total test functions: $TOTAL"

echo
echo "Run full validation: ./run_master_tests.sh --quick"
echo "Start API: ./scripts/start_api"
echo "Health check: python scripts/health_check.py"
