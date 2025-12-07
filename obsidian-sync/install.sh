#!/bin/bash
# Install morning routine launchd agent
# Run this script to set up the 6 AM daily task injection

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.knightsystems.morning-routine.plist"
PLIST_SOURCE="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"
LOG_DIR="$HOME/.local/log/morning-routine"

echo "Installing morning routine launchd agent..."

# Create log directory
mkdir -p "$LOG_DIR"
echo "Created log directory: $LOG_DIR"

# Install Python dependencies for the script
echo "Installing Python dependencies..."
pip3 install --user --break-system-packages requests 2>/dev/null || \
    pip3 install --break-system-packages requests 2>/dev/null || \
    echo "Warning: Could not install requests. Make sure it's available."

# Copy plist to LaunchAgents
if [ -f "$PLIST_DEST" ]; then
    echo "Unloading existing agent..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

cp "$PLIST_SOURCE" "$PLIST_DEST"
echo "Copied plist to: $PLIST_DEST"

# Load the agent
launchctl load "$PLIST_DEST"
echo "Loaded launchd agent"

# Verify
if launchctl list | grep -q "com.knightsystems.morning-routine"; then
    echo ""
    echo "✅ Morning routine agent installed successfully!"
    echo ""
    echo "The morning routine will run daily at 6:00 AM."
    echo ""
    echo "To test manually, run:"
    echo "  python3 $SCRIPT_DIR/scripts/morning_routine.py"
    echo ""
    echo "To view logs:"
    echo "  tail -f $LOG_DIR/morning_routine.log"
    echo ""
    echo "To uninstall:"
    echo "  launchctl unload $PLIST_DEST"
    echo "  rm $PLIST_DEST"
else
    echo "❌ Failed to install launchd agent"
    exit 1
fi
