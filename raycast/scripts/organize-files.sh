#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Organize Files
# @raycast.mode fullOutput

# Optional parameters:
# @raycast.icon 📁
# @raycast.packageName File Classifier
# @raycast.description Scan, review, and organize files from Desktop/Downloads

# Arguments:
# @raycast.argument1 { "type": "text", "placeholder": "Directory (default: Desktop)", "optional": true }

DIR="${1:-~/Desktop}"

cd ~/Dropbox/web-projects/productivity-service

echo "Opening terminal for interactive file organization..."
echo "Directory: $DIR"
echo ""

# Open a new terminal window with the organize command
osascript -e "tell application \"Terminal\"
    activate
    do script \"cd ~/Dropbox/web-projects/productivity-service && uv run python -m filesystem-daemon.cli organize $DIR\"
end tell"

echo "Terminal window opened with organize workflow."
