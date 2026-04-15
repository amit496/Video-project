#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$PWD}"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "Virtualenv missing. Run scripts/gcp_vm_setup.sh first."
  exit 1
fi

echo "Preflight..."
"$ROOT/.venv/bin/python" -m src.main --preflight | tee "$LOG_DIR/preflight.log"

echo "Rendering smoke test (skip YouTube upload)..."
"$ROOT/.venv/bin/python" -m src.main --skip-upload | tee "$LOG_DIR/render.log"

echo "Smoke test finished."
echo "Check:"
echo "- output/ for MP4"
echo "- temp/ for script, voice, staged media, thumbnail"
echo "- logs/render.log for fetch and render details"
