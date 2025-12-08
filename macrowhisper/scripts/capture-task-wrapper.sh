#!/bin/bash
# Wrapper script for Macrowhisper → Raycast Capture Task

INPUT="$1"

# Only proceed if we have content
if [ -n "$INPUT" ]; then
    "$HOME/.config/raycast/scripts/capture-task.sh" "$INPUT"
else
    echo "No task content provided"
fi
