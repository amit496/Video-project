#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$PWD}"

sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip ffmpeg git

python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/requirements.txt"

if [ ! -f "$ROOT/.env" ]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "Created $ROOT/.env from .env.example"
fi

mkdir -p "$ROOT/output" "$ROOT/temp" "$ROOT/logs"

echo "Setup complete."
echo "Next:"
echo "1. Edit $ROOT/.env"
echo "2. Put at least one anchor image in $ROOT/assets/anchor/"
echo "3. Run: bash $ROOT/scripts/gcp_vm_smoke_run.sh $ROOT"
