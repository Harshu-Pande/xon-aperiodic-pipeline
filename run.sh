#!/usr/bin/env bash
# =============================================================================
# One-command launcher for macOS / Linux.
#
#   ./run.sh            -> set up (first time) and process config's input folder
#   ./run.sh gui        -> launch the offline GUI
#   ./run.sh streams f  -> list streams in file f
#   ./run.sh <args...>  -> forwarded to `xon-pipeline`
#
# It creates a self-contained virtual environment in .venv the first time, installs
# dependencies, then runs. No global installs, no git required, safe to re-run.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python 3 was not found. Install Python 3.9+ from https://www.python.org/downloads/ and re-run." >&2
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "First run: creating a virtual environment in .venv (this happens once)…"
  "$PY" -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip >/dev/null
  echo "Installing the pipeline and its dependencies…"
  python -m pip install -e . >/dev/null
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# The GUI needs streamlit (an optional extra); install it on first use so `./run.sh gui`
# just works without anyone having to know about extras.
if [ "${1:-}" = "gui" ]; then
  python -c "import streamlit" >/dev/null 2>&1 || {
    echo "Installing the GUI (streamlit), one time…"
    python -m pip install streamlit >/dev/null
  }
fi

if [ "$#" -eq 0 ]; then
  exec xon-pipeline run
else
  exec xon-pipeline "$@"
fi
