#!/bin/bash
# =============================================================================
#  DOUBLE-CLICK THIS FILE to start the Xon pipeline. No terminal knowledge needed.
#
#  What happens: the first time, it quietly sets itself up (a couple of minutes),
#  then it opens a page in your web browser. In that page you choose the folder
#  with your recordings and press one button. That's it.
#
#  (Others in the lab: you can change the two default folders just below.)
# =============================================================================
cd "$(dirname "$0")"

# Default folders shown in the app (you can change these in the app too).
export XON_DEFAULT_INPUT="$HOME/Downloads/EEG"
export XON_DEFAULT_OUTPUT="$HOME/Desktop/Xon results"

echo "----------------------------------------------------------------"
echo "  Starting the Xon pipeline."
echo "  The FIRST time, setup can take 1-2 minutes. Please wait..."
echo "  A page will open in your web browser when it's ready."
echo "  (Keep this black window open while you use the app.)"
echo "----------------------------------------------------------------"
echo ""

bash run.sh gui
