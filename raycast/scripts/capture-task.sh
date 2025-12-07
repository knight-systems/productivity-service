#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Capture Task
# @raycast.mode silent

# Optional parameters:
# @raycast.icon images/task.png
# @raycast.packageName Productivity
# @raycast.description Capture task to OmniFocus via AI parsing

# Arguments:
# @raycast.argument1 { "type": "text", "placeholder": "Task description" }

TASK="$1"
API="https://el5c54bhs2.execute-api.us-east-1.amazonaws.com/tasks/capture"

if [ -z "$TASK" ]; then
    echo "Error: No task description provided"
    exit 1
fi

RESPONSE=$(curl -s -X POST "$API" \
    -H "Content-Type: application/json" \
    -d "{\"text\": \"$TASK\"}")

# Check if curl succeeded
if [ $? -ne 0 ]; then
    echo "Error: Failed to connect to API"
    exit 1
fi

# Extract message from response
MESSAGE=$(echo "$RESPONSE" | python3 -c "import sys,json; data=json.load(sys.stdin); print(data.get('message', 'Task captured'))" 2>/dev/null)

if [ $? -ne 0 ]; then
    echo "Task sent (could not parse response)"
else
    echo "$MESSAGE"
fi
