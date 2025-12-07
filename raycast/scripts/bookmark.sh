#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Bookmark
# @raycast.mode silent

# Optional parameters:
# @raycast.icon images/bookmark.png
# @raycast.packageName Productivity
# @raycast.description Save bookmark to Obsidian (daily note + permanent file)

# Arguments:
# @raycast.argument1 { "type": "text", "placeholder": "URL" }
# @raycast.argument2 { "type": "text", "placeholder": "Title" }
# @raycast.argument3 { "type": "text", "placeholder": "Notes", "optional": true }

URL="$1"
TITLE="$2"
NOTES="${3:-}"
DATE=$(date +"%Y-%m-%d")

if [ -z "$URL" ] || [ -z "$TITLE" ]; then
    echo "Error: URL and Title are required"
    exit 1
fi

# Build entry for daily note
if [ -n "$NOTES" ]; then
    ENTRY="- [$TITLE]($URL) - $NOTES"
else
    ENTRY="- [$TITLE]($URL)"
fi

# URL encode the entry
ENCODED_ENTRY=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$ENTRY'))")

# Step 1: Ensure daily note exists (workaround for Advanced URI issue #48)
open "obsidian://advanced-uri?vault=Second%20Brain&daily=true&mode=append&data="
sleep 0.5

# Step 2: Append to Bookmarks section
# 🔖 Bookmarks = %F0%9F%94%96%20Bookmarks
open "obsidian://advanced-uri?vault=Second%20Brain&daily=true&heading=%F0%9F%94%96%20Bookmarks&mode=append&data=$ENCODED_ENTRY"

# Step 3: Create permanent bookmark file
# Sanitize title for filename (remove special chars, lowercase, replace spaces with dashes)
SAFE_TITLE=$(echo "$TITLE" | tr -cd '[:alnum:] ' | tr ' ' '-' | tr '[:upper:]' '[:lower:]' | head -c 50)
FILENAME="$DATE-$SAFE_TITLE"

# Build bookmark file content with frontmatter
read -r -d '' BOOKMARK_CONTENT << ENDOFFILE
---
title: $TITLE
url: $URL
tags: [bookmark]
created: $DATE
---

# $TITLE

## Source
$URL

## Notes
$NOTES

## Related

ENDOFFILE

# URL encode the content
ENCODED_CONTENT=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.stdin.read()))" <<< "$BOOKMARK_CONTENT")

# Create the bookmark file
open "obsidian://advanced-uri?vault=Second%20Brain&filepath=Bookmarks/$FILENAME.md&mode=new&data=$ENCODED_CONTENT"

echo "Bookmark saved: $TITLE"
