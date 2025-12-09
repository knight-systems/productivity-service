#!/bin/bash
# Install file classifier daemon as a launchd service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_SRC="$SCRIPT_DIR/launchd/com.knightsystems.file-classifier.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.knightsystems.file-classifier.plist"
LOG_DIR="$HOME/.file-classifier/logs"

echo "File Classifier Daemon Installer"
echo "================================="

# Create log directory
echo "Creating log directory..."
mkdir -p "$LOG_DIR"

# Stop existing service if running
if launchctl list | grep -q "com.knightsystems.file-classifier"; then
    echo "Stopping existing service..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

# Copy plist
echo "Installing launchd plist..."
cp "$PLIST_SRC" "$PLIST_DEST"

# Sync dependencies with UV
echo "Syncing dependencies with UV..."
cd "$SCRIPT_DIR/.."
uv sync

# Initialize database
echo "Initializing database..."
uv run python -m filesystem-daemon.cli init

# Load service
echo "Starting service..."
launchctl load "$PLIST_DEST"

# Check status
sleep 2
if launchctl list | grep -q "com.knightsystems.file-classifier"; then
    echo ""
    echo "Service installed and running!"
    echo ""
    echo "Useful commands:"
    echo "  View logs:      tail -f $LOG_DIR/stdout.log"
    echo "  Check status:   launchctl list | grep file-classifier"
    echo "  Stop service:   launchctl unload $PLIST_DEST"
    echo "  Start service:  launchctl load $PLIST_DEST"
    echo ""
    echo "CLI commands:"
    echo "  uv run python -m filesystem-daemon.cli organize   # Interactive organize workflow"
    echo "  uv run python -m filesystem-daemon.cli pending    # Show pending plans"
    echo "  uv run python -m filesystem-daemon.cli review     # Review pending plans"
else
    echo ""
    echo "Warning: Service may not have started correctly."
    echo "Check logs at: $LOG_DIR/stderr.log"
fi
