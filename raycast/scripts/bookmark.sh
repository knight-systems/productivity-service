#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Bookmark
# @raycast.mode silent

# Optional parameters:
# @raycast.icon images/bookmark.png
# @raycast.packageName Productivity
# @raycast.description Save bookmark to Obsidian via productivity service

# Arguments:
# @raycast.argument1 { "type": "text", "placeholder": "URL" }
# @raycast.argument2 { "type": "text", "placeholder": "Notes", "optional": true }

URL="$1"
NOTES="${2:-}"

if [ -z "$URL" ]; then
    echo "Error: URL is required"
    exit 1
fi

# API endpoint - set via environment or use default
API_URL="${PRODUCTIVITY_API_URL:-https://el5c54bhs2.execute-api.us-east-1.amazonaws.com}"

# Build JSON payload
if [ -n "$NOTES" ]; then
    JSON_PAYLOAD="{\"url\": \"$URL\", \"notes\": \"$NOTES\", \"mode\": \"auto\"}"
else
    JSON_PAYLOAD="{\"url\": \"$URL\", \"mode\": \"auto\"}"
fi

# Make API request
RESPONSE=$(curl -s -X POST "$API_URL/bookmarks/save" \
    -H "Content-Type: application/json" \
    -d "$JSON_PAYLOAD")

# Check for success
if echo "$RESPONSE" | grep -q '"success":true'; then
    TITLE=$(echo "$RESPONSE" | grep -o '"title":"[^"]*"' | head -1 | cut -d'"' -f4)
    echo "Bookmark saved: $TITLE"
else
    ERROR=$(echo "$RESPONSE" | grep -o '"detail":"[^"]*"' | cut -d'"' -f4)
    echo "Error: ${ERROR:-Failed to save bookmark}"
    exit 1
fi
