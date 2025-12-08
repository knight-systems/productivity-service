#!/bin/bash
# Wrapper script for Macrowhisper → Raycast Journal

INPUT="$1"

# Only proceed if we have content
if [ -n "$INPUT" ]; then
    "$HOME/.config/raycast/scripts/journal.sh" "$INPUT"
else
    echo "No journal content provided"
fi
