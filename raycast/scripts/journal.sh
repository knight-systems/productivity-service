#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Journal
# @raycast.mode silent

# Optional parameters:
# @raycast.icon images/journal.png
# @raycast.packageName Productivity
# @raycast.description Add entry to Obsidian Brain Dump

# Arguments:
# @raycast.argument1 { "type": "text", "placeholder": "What's on your mind?" }

ENTRY="$1"

if [ -z "$ENTRY" ]; then
    echo "Error: No entry provided"
    exit 1
fi

TIMESTAMP=$(date +"%H:%M")
FULL_ENTRY="- $TIMESTAMP $ENTRY"

# URL encode the entry
ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$FULL_ENTRY'))")

# Step 1: Ensure daily note exists (workaround for Advanced URI issue #48)
# This creates the daily note if it doesn't exist
open "obsidian://advanced-uri?vault=Second%20Brain&daily=true&mode=append&data="

# Wait for Obsidian to process
sleep 0.5

# Step 2: Append under the Brain Dump heading
# ☕ Brain Dump = %E2%98%95%20Brain%20Dump
open "obsidian://advanced-uri?vault=Second%20Brain&daily=true&heading=%E2%98%95%20Brain%20Dump&mode=append&data=$ENCODED"

echo "Added to Brain Dump"
