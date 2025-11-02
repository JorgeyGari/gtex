#!/usr/bin/env bash
set -euo pipefail

# Convenience wrapper for common uv-managed commands.
# Usage:
#   ./scripts/run.sh sync                # run `uv sync` to create .venv and install deps
#   ./scripts/run.sh main                # run the interactive orchestrator
#   ./scripts/run.sh gdc-dry [N]         # run gdc.py --dry-run --max N (default 10)
#   ./scripts/run.sh gdc [N]             # run gdc.py -y --max N (0 = all)
#   ./scripts/run.sh pytest              # run tests with uv
#   ./scripts/run.sh shell               # open a shell inside the uv-managed environment

CMD=${1:-}

if [[ -z "$CMD" ]]; then
  echo "Usage: $0 {sync|main|gdc-dry|gdc|pytest|shell} [args]"
  exit 1
fi

case "$CMD" in
  sync)
    echo "Running: uv sync"
    uv sync
    ;;

  main)
    echo "Running: uv run python main.py"
    uv run python main.py
    ;;

  gdc-dry)
    N=${2:-10}
    echo "Running: uv run python gdc.py --dry-run --max $N"
    uv run python gdc.py --dry-run --max "$N"
    ;;

  gdc)
    N=${2:-0}
    echo "Running: uv run python gdc.py -y --max $N"
    uv run python gdc.py -y --max "$N"
    ;;

  pytest)
    echo "Running: uv run pytest"
    uv run pytest
    ;;

  shell)
    echo "Starting a shell inside uv-managed environment (type exit to return)"
    uv run bash
    ;;

  *)
    echo "Unknown command: $CMD"
    echo "Usage: $0 {sync|main|gdc-dry|gdc|pytest|shell} [args]"
    exit 2
    ;;
esac
