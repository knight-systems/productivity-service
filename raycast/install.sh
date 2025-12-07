#!/bin/bash
# Install Raycast Script Commands via symlinks
# Works on both personal and work Macs
#
# Usage:
#   ./raycast/install.sh
#
# This script creates symlinks from the repo to Raycast's script directory,
# enabling the same scripts to be used across multiple machines via git.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAYCAST_SCRIPTS_DIR="$HOME/.config/raycast/scripts"

echo "=========================================="
echo "  Raycast Script Commands Installer"
echo "=========================================="
echo ""
echo "Source: $SCRIPT_DIR/scripts"
echo "Target: $RAYCAST_SCRIPTS_DIR"
echo ""

# Create Raycast scripts directory if needed
if [ ! -d "$RAYCAST_SCRIPTS_DIR" ]; then
    echo "Creating Raycast scripts directory..."
    mkdir -p "$RAYCAST_SCRIPTS_DIR"
fi

# Create images directory for icons
if [ ! -d "$SCRIPT_DIR/images" ]; then
    echo "Creating images directory..."
    mkdir -p "$SCRIPT_DIR/images"
fi

# Symlink each script
echo "Installing scripts..."
for script in "$SCRIPT_DIR/scripts/"*.sh; do
    if [ -f "$script" ]; then
        script_name=$(basename "$script")
        target="$RAYCAST_SCRIPTS_DIR/$script_name"

        # Remove existing symlink or file
        if [ -L "$target" ]; then
            echo "  Updating symlink: $script_name"
            rm "$target"
        elif [ -f "$target" ]; then
            echo "  Replacing file: $script_name"
            rm "$target"
        else
            echo "  Creating: $script_name"
        fi

        # Create symlink
        ln -s "$script" "$target"
    fi
done

# Make scripts executable
echo ""
echo "Setting executable permissions..."
chmod +x "$SCRIPT_DIR/scripts/"*.sh

echo ""
echo "=========================================="
echo "  Installation complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Open Raycast (Cmd+Space or your hotkey)"
echo ""
echo "2. Search for 'Reload Script Commands' and run it"
echo "   OR go to Extensions > Script Commands > Reload"
echo ""
echo "3. If this is your first time:"
echo "   - Go to Raycast Settings > Extensions"
echo "   - Click 'Script Commands'"
echo "   - Click 'Add Directories'"
echo "   - Add: $RAYCAST_SCRIPTS_DIR"
echo ""
echo "4. Test by searching for:"
echo "   - 'Capture Task' - Send task to OmniFocus"
echo "   - 'Journal' - Add to Obsidian Brain Dump"
echo "   - 'Bookmark' - Save URL to Obsidian"
echo "   - 'Quick Log' - Add to daily note section"
echo ""
echo "Tip: Assign hotkeys to frequently used commands!"
echo "     Raycast Settings > Extensions > Script Commands"
echo ""
