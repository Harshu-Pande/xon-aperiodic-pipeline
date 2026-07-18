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

# If this folder was downloaded (e.g. a ZIP), macOS may have "quarantined" it, which
# is what triggers the scary "unidentified developer" warning. Clear that flag on our
# own folder so it never nags again. (No admin rights needed; ignores failure silently.)
xattr -dr com.apple.quarantine "$(pwd)" >/dev/null 2>&1 || true

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python 3 was not found. Install Python 3.9+ from https://www.python.org/downloads/ and re-run." >&2
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "First run: setting up (this happens once)…"
  # --system-site-packages reuses any scientific packages already installed (e.g. a conda
  # base with numpy/scipy/matplotlib/pandas), so setup installs only the few missing pieces
  # instead of rebuilding the whole stack. Much faster.
  "$PY" -m venv --system-site-packages .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip >/dev/null 2>&1 || true
  echo "Installing the pipeline (only what's missing)…"
  python -m pip install -e . >/dev/null
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# The desktop GUI uses optional drag-and-drop support (tiny, fast). Install once; the GUI
# works without it too (falls back to Browse buttons).
if [ "${1:-}" = "gui" ]; then
  python -c "import tkinterdnd2" >/dev/null 2>&1 || python -m pip install tkinterdnd2 >/dev/null 2>&1 || true
fi

if [ "$#" -eq 0 ]; then
  exec xon-pipeline run
else
  exec xon-pipeline "$@"
fi
