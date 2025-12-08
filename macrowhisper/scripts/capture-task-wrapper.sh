#!/bin/bash
# Wrapper script for Macrowhisper → Raycast Capture Task
# Strips trigger phrases like "task:", "add task:", "capture task:"

INPUT="$1"

# Strip common trigger prefixes (case insensitive)
TASK=$(echo "$INPUT" | sed -E 's/^(task|add task|capture task)[[:space:]]*[:.]?[[:space:]]*//i')

# Only proceed if we have content after stripping
if [ -n "$TASK" ]; then
    "$HOME/.config/raycast/scripts/capture-task.sh" "$TASK"
else
    echo "No task content provided"
fi
