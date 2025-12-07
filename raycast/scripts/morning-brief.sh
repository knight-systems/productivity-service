#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Morning Brief
# @raycast.mode compact

# Optional parameters:
# @raycast.icon ☀️
# @raycast.packageName Productivity
# @raycast.description Generate morning brief with OmniFocus tasks + AI summary

SCRIPT_DIR="$(dirname "$(dirname "$(readlink -f "$0" || echo "$0")")")"
MORNING_SCRIPT="$SCRIPT_DIR/../obsidian-sync/scripts/morning_routine.py"

# Check if script exists
if [ ! -f "$MORNING_SCRIPT" ]; then
    # Try alternative path
    MORNING_SCRIPT="$HOME/Dropbox/web-projects/productivity-service/obsidian-sync/scripts/morning_routine.py"
fi

if [ ! -f "$MORNING_SCRIPT" ]; then
    echo "Error: morning_routine.py not found"
    exit 1
fi

echo "Generating morning brief..."

# Run the morning routine script
OUTPUT=$(python3 "$MORNING_SCRIPT" 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "Morning brief generated ✓"
else
    echo "Failed: Check logs at ~/.local/log/morning-routine/"
    exit 1
fi
