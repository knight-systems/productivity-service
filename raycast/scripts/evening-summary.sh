#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Evening Summary
# @raycast.mode compact

# Optional parameters:
# @raycast.icon 🌙
# @raycast.packageName Productivity
# @raycast.description Extract action items from daily note and generate summary

API_URL="https://el5c54bhs2.execute-api.us-east-1.amazonaws.com"

echo "Generating evening summary..."

# Call the evening summary API
RESPONSE=$(curl -s -X POST "$API_URL/routines/evening-summary" \
    -H "Content-Type: application/json" \
    -d '{"extract_tasks": true, "generate_summary": true}')

# Check if successful
SUCCESS=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('success', False))" 2>/dev/null)

if [ "$SUCCESS" = "True" ]; then
    TASKS_SENT=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('tasks_sent', 0))" 2>/dev/null)
    echo "Evening summary complete ✓ ($TASKS_SENT tasks → OmniFocus)"
else
    MESSAGE=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('message', 'Unknown error'))" 2>/dev/null)
    echo "Failed: $MESSAGE"
    exit 1
fi
