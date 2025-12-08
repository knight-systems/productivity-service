# Macrowhisper Integration

Integrates [Superwhisper](https://superwhisper.com) voice modes with Raycast commands via [Macrowhisper](https://github.com/ognistik/macrowhisper).

## How It Works

```
Superwhisper (voice) → Macrowhisper (mode trigger) → Wrapper Script → Raycast Command → Action
```

1. **Superwhisper** captures voice and transcribes it
2. **Modes** (Task, Journal) trigger specific actions based on spoken keywords
3. **Macrowhisper** watches Superwhisper output and routes to shell scripts
4. **Wrapper scripts** strip trigger phrases and call Raycast commands
5. **Raycast commands** send to API/Obsidian

## Prerequisites

- [Superwhisper](https://superwhisper.com) - Voice transcription
- [Macrowhisper](https://github.com/ognistik/macrowhisper) - Mode routing
- Raycast scripts installed (`./raycast/install.sh`)

## Installation

```bash
# 1. Install Macrowhisper (if not already)
curl -L https://raw.githubusercontent.com/ognistik/macrowhisper/main/scripts/install.sh | sudo sh

# 2. Install Raycast scripts first
./raycast/install.sh

# 3. Install Macrowhisper integration
./macrowhisper/install.sh
```

> **Note**: The install script is idempotent. Re-run it anytime to pick up new scripts or config changes from the repo.

## Superwhisper Mode Configuration

After running the install script, configure Superwhisper modes:

### Task Mode

Captures tasks and sends to OmniFocus via the productivity API.

1. Open Superwhisper Preferences
2. Go to Modes
3. Create new mode:
   - **Name**: `Task`
   - **Trigger phrase**: `task` (spoken at start)
   - **Action**: None (let Macrowhisper handle it)

**Usage**: "Task buy groceries tomorrow for errands"

### Journal Mode

Adds entries to Obsidian's daily note Brain Dump section.

1. Create new mode:
   - **Name**: `Journal`
   - **Trigger phrase**: `journal`
   - **Action**: None

**Usage**: "Journal had a productive morning meeting"

## Files

```
macrowhisper/
├── install.sh                    # Installation script
├── macrowhisper.template.json    # Config template ({{HOME}} placeholders)
├── scripts/
│   ├── capture-task-wrapper.sh   # Strips "task:" prefix, calls Raycast
│   └── journal-wrapper.sh        # Strips "journal:" prefix, calls Raycast
└── README.md                     # This file
```

## Configuration

The install script generates `~/.config/macrowhisper/macrowhisper.json` from the template.

Key settings:
- `defaults.watch`: Directory Superwhisper writes transcriptions to
- `scriptsShell.captureTask.triggerModes`: "Task" - triggers on Task mode
- `scriptsShell.journal.triggerModes`: "Journal" - triggers on Journal mode

## Wrapper Scripts

Wrapper scripts strip common trigger phrases before passing to Raycast:

**capture-task-wrapper.sh** strips:
- "task:"
- "add task:"
- "capture task:"

**journal-wrapper.sh** strips:
- "journal:"
- "brain dump:"
- "log:"

This allows natural speech like "Task: buy milk" to become just "buy milk".

## Troubleshooting

### Check Macrowhisper Status

```bash
macrowhisper status
```

### View Logs

```bash
macrowhisper logs
```

### Test Wrapper Scripts Manually

```bash
# Test task capture
~/.config/macrowhisper/scripts/capture-task-wrapper.sh "task: buy groceries tomorrow"

# Test journal
~/.config/macrowhisper/scripts/journal-wrapper.sh "journal: had a great meeting"
```

### Common Issues

1. **"No task content provided"** - The trigger phrase wasn't detected. Check Superwhisper mode name matches "Task" exactly.

2. **Raycast script not found** - Run `./raycast/install.sh` first.

3. **Nothing happens when speaking** - Ensure Superwhisper output directory matches `defaults.watch` in config.

## Adding New Modes

To add a new mode (e.g., "Bookmark"):

1. Create Superwhisper mode named "Bookmark"

2. Add wrapper script `scripts/bookmark-wrapper.sh`:
   ```bash
   #!/bin/bash
   INPUT="$1"
   URL=$(echo "$INPUT" | sed -E 's/^bookmark[[:space:]]*[:.]?[[:space:]]*//i')
   if [ -n "$URL" ]; then
       "$HOME/.config/raycast/scripts/bookmark.sh" "$URL"
   fi
   ```

3. Add to `macrowhisper.template.json`:
   ```json
   "bookmark": {
     "action": "{{HOME}}/.config/macrowhisper/scripts/bookmark-wrapper.sh \"{{swResult}}\"",
     "triggerModes": "Bookmark"
   }
   ```

4. Re-run `./macrowhisper/install.sh`

## Related

- [Raycast Scripts](../raycast/README.md) - Raycast command documentation
- [Productivity Service](../README.md) - API documentation
