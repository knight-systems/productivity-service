# Raycast Script Commands

Raycast Script Commands for productivity workflows. These scripts integrate with the productivity service API and Obsidian.

## Quick Start

```bash
# From the productivity-service repo root
./raycast/install.sh
```

This creates symlinks to `~/.config/raycast/scripts/`, enabling the same setup across multiple machines.

## Available Commands

| Command | Description | Hotkey Suggestion |
|---------|-------------|-------------------|
| **Organize Files** | Scan, review, and organize Desktop/Downloads | `⌥⌘O` |
| **Capture Task** | Send task to OmniFocus via AI parsing | `⌥⌘T` |
| **Journal** | Add entry to Obsidian Brain Dump | `⌥⌘J` |
| **Bookmark** | Save URL to Obsidian (dual storage) | `⌥⌘B` |
| **Quick Log** | Add to specific daily note section | `⌥⌘L` |
| **Morning Brief** | Generate morning summary | `⌥⌘M` |
| **Evening Summary** | Generate evening summary | `⌥⌘E` |

## Prerequisites

- [Raycast](https://raycast.com) installed
- [Obsidian](https://obsidian.md) with vault named "Second Brain"
- [Advanced URI plugin](https://github.com/Vinzent03/obsidian-advanced-uri) installed in Obsidian
- Productivity service API deployed (for Capture Task)

## Command Details

### Organize Files

Opens a terminal with the interactive file organization workflow. Scans Desktop (or specified directory), classifies files using rules + AI, and lets you review/modify plans before executing.

**Usage:** `Organize Files` or `Organize Files ~/Downloads`

**Workflow:**
1. Scans directory and classifies files
2. Auto-approves obvious deletes (screenshots, installers)
3. Interactive review of moves with keyboard shortcuts
4. Execute approved actions

### Capture Task

Captures a task to OmniFocus via the productivity service API.

**Usage:** `Capture Task buy milk tomorrow for groceries`

The AI parses:
- Task title
- Project (if mentioned)
- Due date (if mentioned)
- Tags (if mentioned)

### Journal

Adds a timestamped entry to your Obsidian daily note under `## ☕ Brain Dump`.

**Usage:** `Journal had a great meeting about the project`

**Result in daily note:**
```markdown
## ☕ Brain Dump
- 14:32 had a great meeting about the project
```

### Bookmark

Saves a bookmark with dual storage:
1. Reference in daily note under `## 🔖 Bookmarks`
2. Permanent file in `Bookmarks/` folder with frontmatter

**Usage:** `Bookmark https://example.com "Article Title" "Great explanation"`

### Quick Log

Adds an entry to a specific section of your daily note.

**Sections:**
- Brain Dump (`## ☕ Brain Dump`)
- Journal (`## 📝 Journal & Reflection`)
- Tasks (`## 📋 Today's Tasks (from OmniFocus)`)
- Morning Plan (`## 🌅 Morning Plan`)

## Configuration

### Obsidian Vault Name

If your vault isn't named "Second Brain", update the vault name in each script:

```bash
# In each .sh file, change:
vault=Second%20Brain
# to your URL-encoded vault name
```

### API Endpoint

The API endpoint is configured in `capture-task.sh`:

```bash
API="https://el5c54bhs2.execute-api.us-east-1.amazonaws.com/tasks/capture"
```

## Troubleshooting

### Scripts not appearing in Raycast

1. Run the install script: `./raycast/install.sh`
2. In Raycast, search "Reload Script Commands"
3. Check that `~/.config/raycast/scripts/` is added as a script directory

### Obsidian not opening

- Ensure Obsidian is running
- Check that Advanced URI plugin is installed and enabled
- Verify vault name matches your actual vault

### Daily note heading not found

The scripts use a two-step workaround for [Advanced URI issue #48](https://github.com/Vinzent03/obsidian-advanced-uri/issues/48):
1. First creates/opens the daily note
2. Then appends under the heading

If entries appear at the bottom instead of under headings, ensure your daily note template includes the expected headings.

## Multi-Machine Setup

Since scripts are symlinked from this repo, you can sync across machines:

1. Clone this repo on each machine
2. Run `./raycast/install.sh`
3. Pull updates to get script changes

## Related

- [Filesystem Daemon Documentation](../filesystem-daemon/README.md) - Full CLI reference for file organization
- [Productivity Service API](../README.md) - Main project documentation
- [Raycast Script Commands Repo](https://github.com/raycast/script-commands)
- [Obsidian Advanced URI](https://github.com/Vinzent03/obsidian-advanced-uri)
