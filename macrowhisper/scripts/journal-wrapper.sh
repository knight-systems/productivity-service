#!/bin/bash
# Wrapper script for Macrowhisper → Raycast Journal
# Strips trigger phrases like "journal:", "brain dump:", "log:"

INPUT="$1"

# Strip common trigger prefixes (case insensitive)
ENTRY=$(echo "$INPUT" | sed -E 's/^(journal|brain dump|log)[[:space:]]*[:.]?[[:space:]]*//i')

# Only proceed if we have content after stripping
if [ -n "$ENTRY" ]; then
    "$HOME/.config/raycast/scripts/journal.sh" "$ENTRY"
else
    echo "No journal content provided"
fi
