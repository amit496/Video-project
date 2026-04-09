#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT/logs"

echo "Preflight..."
"$ROOT/.venv/bin/python" -m src.main --preflight

echo "Run (no upload)..."
"$ROOT/.venv/bin/python" -m src.main --skip-upload >> "$ROOT/logs/run.log" 2>&1

echo "Done. Check output/ and temp/."

