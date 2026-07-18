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

# ---------------------------------------------------------------------------
# AUTO-UPDATE (smart): pulls the latest code from GitHub but PRESERVES any changes you
# made locally (config.yaml or src). Handled by update.py. Only public code is fetched;
# your data/outputs/.venv are never touched (HIPAA-safe). Set XON_NO_UPDATE=1 to freeze.
# ---------------------------------------------------------------------------
if [ "${XON_NO_UPDATE:-0}" != "1" ] && [ "${XON_UPDATED:-0}" != "1" ] && [ -f update.py ]; then
  rc=0; "$PY" update.py || rc=$?
  if [ "$rc" = "10" ]; then
    export XON_UPDATED=1
    chmod +x run.sh "Start Here (Mac).command" 2>/dev/null || true
    exec bash run.sh "$@"
  fi
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
  # Install DEPENDENCIES only (not the package). We run the code straight from src/ via
  # PYTHONPATH below, which is far more reliable than pip's editable-install console script.
  python -m pip install -r requirements.txt >/dev/null
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
  # if we just auto-updated, catch any new dependencies (code runs live from src/)
  [ "${XON_UPDATED:-0}" = "1" ] && python -m pip install -r requirements.txt >/dev/null 2>&1 || true
fi

# The desktop GUI uses optional drag-and-drop support (tiny, fast). Install once; the GUI
# works without it too (falls back to Browse buttons).
if [ "${1:-}" = "gui" ]; then
  python -c "import tkinterdnd2" >/dev/null 2>&1 || python -m pip install tkinterdnd2 >/dev/null 2>&1 || true
fi

# Create a one-double-click Desktop launcher so opening it again tomorrow is trivial
# (no re-running any command). Created once; it just re-invokes this folder's run.sh.
DESKTOP_LAUNCHER="$HOME/Desktop/Open Xon Pipeline.command"
if [ ! -e "$DESKTOP_LAUNCHER" ] && [ -d "$HOME/Desktop" ]; then
  {
    echo "#!/bin/bash"
    echo "cd \"$(pwd)\""
    echo "bash run.sh gui"
  } > "$DESKTOP_LAUNCHER" 2>/dev/null && chmod +x "$DESKTOP_LAUNCHER" 2>/dev/null || true
  echo "Tip: a shortcut 'Open Xon Pipeline' was placed on your Desktop — double-click it next time."
fi

# Run the code straight from src/ (robust: no dependency on an editable-install console
# script). PYTHONPATH is also inherited by parallel worker processes and the web GUI.
export PYTHONPATH="$(pwd)/src${PYTHONPATH:+:$PYTHONPATH}"
if [ "$#" -eq 0 ]; then
  exec python -m xon_aperiodic.cli run
else
  exec python -m xon_aperiodic.cli "$@"
fi
