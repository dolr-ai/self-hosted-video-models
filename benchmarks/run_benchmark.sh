#!/bin/bash
#
# LTX-2 Portrait 1080p Benchmark Runner
#
# Runs both T2V and TI2V benchmarks with torch.compile warmup
# Each config: 3 warmup runs + 3 timed runs
#
# Usage:
#   ./run_benchmark.sh                              # All modes, localhost
#   ./run_benchmark.sh http://server:8188           # All modes, custom server
#   ./run_benchmark.sh http://server:8188 t2v       # T2V only
#   ./run_benchmark.sh http://server:8188 ti2v      # TI2V only
#

set -e

SERVER="${1:-http://localhost:8188}"
MODE="${2:-all}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="benchmark_results_${MODE}_${TIMESTAMP}.json"

echo "=============================================="
echo "LTX-2 Portrait 1080p Benchmark"
echo "=============================================="
echo "Server: $SERVER"
echo "Mode:   $MODE"
echo "Output: $OUTPUT_FILE"
echo ""
echo "Each config runs:"
echo "  - 3 warmup runs (first includes torch.compile)"
echo "  - 3 timed runs (for statistical measurement)"
echo ""

# Install dependencies if needed
pip install websocket-client requests Pillow --quiet 2>/dev/null || true

# Run benchmark
python3 "$(dirname "$0")/ltx2_portrait_benchmark.py" \
    --server "$SERVER" \
    --mode "$MODE" \
    --output "$OUTPUT_FILE"

echo ""
echo "Benchmark complete! Results saved to: $OUTPUT_FILE"
