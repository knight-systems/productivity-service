#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Quick Log
# @raycast.mode silent

# Optional parameters:
# @raycast.icon images/log.png
# @raycast.packageName Productivity
# @raycast.description Add entry to a specific daily note section

# Arguments:
# @raycast.argument1 { "type": "dropdown", "placeholder": "Section", "data": [{"title": "Brain Dump", "value": "brain-dump"}, {"title": "Journal", "value": "journal"}, {"title": "Tasks", "value": "tasks"}, {"title": "Morning Plan", "value": "morning"}] }
# @raycast.argument2 { "type": "text", "placeholder": "Entry" }

SECTION="$1"
ENTRY="$2"

if [ -z "$SECTION" ] || [ -z "$ENTRY" ]; then
    echo "Error: Section and entry are required"
    exit 1
fi

# Map section choice to URL-encoded heading
case "$SECTION" in
    "brain-dump")
        # ☕ Brain Dump
        HEADING="%E2%98%95%20Brain%20Dump"
        ;;
    "journal")
        # 📝 Journal & Reflection
        HEADING="%F0%9F%93%9D%20Journal%20%26%20Reflection"
        ;;
    "tasks")
        # 📋 Today's Tasks (from OmniFocus)
        HEADING="%F0%9F%93%8B%20Today%27s%20Tasks%20%28from%20OmniFocus%29"
        ;;
    "morning")
        # 🌅 Morning Plan
        HEADING="%F0%9F%8C%85%20Morning%20Plan"
        ;;
    *)
        echo "Error: Unknown section '$SECTION'"
        exit 1
        ;;
esac

TIMESTAMP=$(date +"%H:%M")
FULL_ENTRY="- $TIMESTAMP $ENTRY"

# URL encode the entry
ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$FULL_ENTRY'))")

# Step 1: Ensure daily note exists (workaround for Advanced URI issue #48)
open "obsidian://advanced-uri?vault=Second%20Brain&daily=true&mode=append&data="
sleep 0.5

# Step 2: Append under the selected heading
open "obsidian://advanced-uri?vault=Second%20Brain&daily=true&heading=$HEADING&mode=append&data=$ENCODED"

echo "Logged to $SECTION"
