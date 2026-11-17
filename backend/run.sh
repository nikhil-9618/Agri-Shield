#!/usr/bin/env bash
# Start the AgriShield API. Creates the virtualenv and .env on first run.
#
#   ./backend/run.sh                 # http://0.0.0.0:8000
#   PORT=9000 ./backend/run.sh
set -euo pipefail

cd "$(dirname "$0")"
REPO_ROOT="$(cd .. && pwd)"
VENV="$REPO_ROOT/.venv"
PY="$VENV/bin/python"

if [ ! -x "$PY" ]; then
  echo "creating virtualenv at $VENV"
  python3 -m venv "$VENV"
  "$PY" -m pip install --upgrade pip
  "$PY" -m pip install -r requirements.txt
fi

if [ ! -f .env ]; then
  echo "no backend/.env found, copying .env.example (edit SECRET_KEY before production)"
  cp .env.example .env
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
echo "AgriShield API on http://$HOST:$PORT (docs at /docs)"
exec "$PY" -m uvicorn app.main:app --host "$HOST" --port "$PORT"
