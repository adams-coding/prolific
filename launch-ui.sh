#!/usr/bin/env bash
set -euo pipefail

# Prolific: Git Active — one-command UI launcher for Linux
# - Creates .venv if missing
# - Installs this project into the venv (editable)
# - Launches the UI
#
# Note: on some distros you may need Tkinter (often package: python3-tk).

cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "ERROR: python3 not found." >&2
  exit 1
fi

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Creating virtual environment..."
  "$PYTHON" -m venv .venv
fi

echo "Installing/Updating app in venv..."
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install -e .

echo "Launching UI..."
if [[ -x ".venv/bin/prolific-agent-ui" ]]; then
  .venv/bin/prolific-agent-ui
else
  .venv/bin/python -m prolific_agent.ui
fi


