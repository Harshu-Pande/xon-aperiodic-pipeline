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

# ---------------------------------------------------------------------------
# AUTO-UPDATE: keep the CODE in sync with GitHub (your data/outputs/.venv are never
# touched). Only the public code is fetched — no patient data ever leaves the machine,
# so this is HIPAA-safe. Set XON_NO_UPDATE=1 to freeze a version (e.g. for a paper).
# ---------------------------------------------------------------------------
REPO="Harshu-Pande/xon-aperiodic-pipeline"
if [ "${XON_NO_UPDATE:-0}" != "1" ] && [ "${XON_UPDATED:-0}" != "1" ]; then
  latest="$(curl -fsS --max-time 6 "https://api.github.com/repos/$REPO/commits/main" 2>/dev/null \
            | sed -n 's/.*"sha": *"\([0-9a-f]\{7,\}\)".*/\1/p' | head -1 || true)"
  current="$(cat .xon_version 2>/dev/null || true)"
  if [ -n "$latest" ] && [ -z "$current" ]; then
    # Freshly installed — just record the version; don't re-download what we just got.
    echo "$latest" > .xon_version 2>/dev/null || true
  elif [ -n "$latest" ] && [ "$latest" != "$current" ]; then
    echo "Updating to the latest version…"
    tmp="$(mktemp -d)"
    if curl -fsSL --max-time 90 "https://github.com/$REPO/archive/refs/heads/main.zip" -o "$tmp/u.zip" \
       && unzip -oq "$tmp/u.zip" -d "$tmp"; then
      src="$tmp/xon-aperiodic-pipeline-main"
      [ -f config/config.yaml ] && cp -f config/config.yaml config/config.yaml.bak 2>/dev/null || true
      if command -v rsync >/dev/null 2>&1; then
        rsync -a --exclude '.venv' --exclude 'data' --exclude 'outputs' --exclude '.xon_version' \
              --exclude '.git' "$src"/ ./ 2>/dev/null || true
      else
        cp -Rf "$src"/src "$src"/config "$src"/docs "$src"/examples "$src"/tests \
               "$src"/*.sh "$src"/*.bat "$src"/*.toml "$src"/*.md "$src"/*.command . 2>/dev/null || true
      fi
      echo "$latest" > .xon_version 2>/dev/null || true
      chmod +x run.sh "Start Here (Mac).command" 2>/dev/null || true
      rm -rf "$tmp"
      echo "Updated. Restarting…"
      export XON_UPDATED=1
      exec bash run.sh "$@"
    fi
    rm -rf "$tmp" 2>/dev/null || true
  fi
fi

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
