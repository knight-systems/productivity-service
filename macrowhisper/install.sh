#!/bin/bash
# Install Macrowhisper configuration and scripts
# Integrates Superwhisper voice modes with Raycast commands
#
# This script is IDEMPOTENT - safe to run multiple times.
# Re-running will update symlinks and config to latest versions.
#
# Prerequisites:
#   - Macrowhisper installed (see below)
#   - Superwhisper installed with "Task" and "Journal" modes configured
#   - Raycast scripts installed: ./raycast/install.sh
#
# Usage:
#   ./macrowhisper/install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MACROWHISPER_CONFIG_DIR="$HOME/.config/macrowhisper"
MACROWHISPER_SCRIPTS_DIR="$MACROWHISPER_CONFIG_DIR/scripts"

echo "=========================================="
echo "  Macrowhisper Integration Installer"
echo "=========================================="
echo ""
echo "Source: $SCRIPT_DIR"
echo "Target: $MACROWHISPER_CONFIG_DIR"
echo ""

# Check if macrowhisper is installed
if ! command -v macrowhisper &> /dev/null; then
    echo "ERROR: Macrowhisper is not installed."
    echo ""
    echo "Install with:"
    echo "  curl -L https://raw.githubusercontent.com/ognistik/macrowhisper/main/scripts/install.sh | sudo sh"
    echo ""
    echo "See: https://github.com/ognistik/macrowhisper"
    exit 1
fi

# Check if Raycast scripts are installed
if [ ! -f "$HOME/.config/raycast/scripts/capture-task.sh" ]; then
    echo "WARNING: Raycast scripts not found."
    echo ""
    echo "Run: ./raycast/install.sh first"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create directories (idempotent)
mkdir -p "$MACROWHISPER_CONFIG_DIR"
mkdir -p "$MACROWHISPER_SCRIPTS_DIR"

# Install wrapper scripts via symlinks (idempotent)
echo "Installing wrapper scripts..."
SCRIPTS_UPDATED=0
for script in "$SCRIPT_DIR/scripts/"*.sh; do
    if [ -f "$script" ]; then
        script_name=$(basename "$script")
        target="$MACROWHISPER_SCRIPTS_DIR/$script_name"

        # Check if symlink already points to correct location
        if [ -L "$target" ] && [ "$(readlink "$target")" = "$script" ]; then
            echo "  Up to date: $script_name"
        else
            # Remove existing symlink or file
            if [ -L "$target" ] || [ -f "$target" ]; then
                rm "$target"
                echo "  Updating: $script_name"
            else
                echo "  Creating: $script_name"
            fi
            ln -s "$script" "$target"
            SCRIPTS_UPDATED=1
        fi

        chmod +x "$script"
    fi
done

# Generate config from template (idempotent with smart diff)
echo ""
echo "Checking configuration..."
CONFIG_FILE="$MACROWHISPER_CONFIG_DIR/macrowhisper.json"
TEMP_CONFIG="/tmp/macrowhisper.json.new"

# Generate new config to temp file
sed "s|{{HOME}}|$HOME|g" "$SCRIPT_DIR/macrowhisper.template.json" > "$TEMP_CONFIG"

if [ -f "$CONFIG_FILE" ]; then
    # Compare existing config with new template
    if diff -q "$CONFIG_FILE" "$TEMP_CONFIG" > /dev/null 2>&1; then
        echo "  Config up to date"
        rm "$TEMP_CONFIG"
    else
        echo "  Config has changed - updating"
        echo "  Backup: $CONFIG_FILE.backup"
        cp "$CONFIG_FILE" "$CONFIG_FILE.backup"
        mv "$TEMP_CONFIG" "$CONFIG_FILE"
    fi
else
    echo "  Creating: $CONFIG_FILE"
    mv "$TEMP_CONFIG" "$CONFIG_FILE"
fi

# Create superwhisper watch directory if needed (idempotent)
WATCH_DIR="$HOME/Documents/superwhisper"
if [ ! -d "$WATCH_DIR" ]; then
    echo ""
    echo "Creating Superwhisper watch directory..."
    mkdir -p "$WATCH_DIR"
    echo "  Created: $WATCH_DIR"
fi

echo ""
echo "=========================================="
echo "  Installation complete!"
echo "=========================================="
echo ""
echo "If this is your first time, configure Superwhisper modes:"
echo ""
echo "1. Open Superwhisper preferences"
echo ""
echo "2. Create 'Task' mode:"
echo "   - Name: Task"
echo "   - Trigger: Say 'task' before your command"
echo "   - Action: None (Macrowhisper handles it)"
echo ""
echo "3. Create 'Journal' mode:"
echo "   - Name: Journal"
echo "   - Trigger: Say 'journal' before your command"
echo "   - Action: None (Macrowhisper handles it)"
echo ""
echo "4. Set Superwhisper output directory:"
echo "   - Preferences > Advanced > Output Directory"
echo "   - Set to: $WATCH_DIR"
echo ""
echo "Testing:"
echo ""
echo "1. Activate Superwhisper (your hotkey)"
echo "2. Say: 'Task buy groceries tomorrow'"
echo "3. Should create task in OmniFocus"
echo ""
echo "4. Say: 'Journal had a productive morning'"
echo "5. Should add to Obsidian Brain Dump"
echo ""
echo "Troubleshooting:"
echo ""
echo "- Check Macrowhisper is running: macrowhisper status"
echo "- View logs: macrowhisper logs"
echo "- Config location: $CONFIG_FILE"
echo ""
