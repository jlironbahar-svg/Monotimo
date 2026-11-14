#!/usr/bin/env bash
# Desktop Friend PC agent launcher (macOS / Linux).
# Creates a virtual environment on first run, installs dependencies, then starts the agent.
# Extra arguments are passed through, e.g.  ./start.sh --headless
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python 3.10+ is required. Install it from https://www.python.org/downloads/ and try again." >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Creating virtual environment (.venv)..."
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# Reinstall dependencies only when requirements.txt changes.
STAMP=.venv/.requirements.sha
CURRENT="$(python -c 'import hashlib;print(hashlib.sha256(open("requirements.txt","rb").read()).hexdigest())')"
if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$CURRENT" ]; then
  echo "Installing dependencies..."
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r requirements.txt
  echo "$CURRENT" > "$STAMP"
fi

[ -f .env ] || cp .env.example .env
exec python -m desktop_friend "$@"
