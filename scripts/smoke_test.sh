#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Running unit tests..."
"$ROOT/.venv/bin/python" -m pytest -q

echo "Dry-run (news fetch only)..."
"$ROOT/.venv/bin/python" -m src.main --dry-run || true

echo "Smoke OK (unit tests passed)."

