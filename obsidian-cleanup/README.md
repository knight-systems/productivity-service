# Obsidian Cleanup

Organize misplaced notes in your Obsidian vault into the correct Areas folders using metadata analysis and AI content classification.

## Quick Start

```bash
# From the productivity-service repo root
cd ~/Dropbox/web-projects/productivity-service

# Initialize (first time)
uv run python -m obsidian-cleanup.cli init

# Run organize workflow
uv run python -m obsidian-cleanup.cli organize
```

## Features

- **Rule-based classification** from frontmatter (category, tags) and filename patterns
- **AI-powered fallback** for notes with insufficient metadata (uses Claude via Bedrock)
- **Interactive review** before moving any files
- **Learns from corrections** to improve future classifications

## How It Works

1. **Scan** - Finds all markdown notes not in protected folders
2. **Classify** - Uses rules first, then AI for low-confidence notes
3. **Review** - Interactive approval of proposed moves
4. **Execute** - Moves approved notes to target folders

### Classification Priority

1. **Protected folders** (skip) - Daily notes, templates, .obsidian
2. **Frontmatter category** (95% confidence) - `category: finance` → 41-Finance
3. **Frontmatter tags** (90% confidence) - Tags containing domain keywords
4. **Filename patterns** (80% confidence) - Keywords like "trading", "health", "resume"
5. **AI content analysis** (for <70% confidence) - Reads note content and classifies

## Area Folders

| Folder | Description |
|--------|-------------|
| 41 - Finance | Trading, investments, budgeting |
| 42 - Family | Kids, family events, home |
| 43 - Work | Career, job, professional |
| 44 - Health | Medical, fitness, mental health |
| 45 - Learning | Courses, tutorials, study notes |
| 46 - Projects | Personal projects, hobbies |

## CLI Commands

| Command | Description |
|---------|-------------|
| `init` | Initialize database, verify vault |
| `organize [path]` | Scan → review → execute workflow |
| `pending` | Show pending plans |
| `show ID` | Show plan details |
| `review` | Interactive review of pending plans |
| `revise ID "feedback"` | Reclassify with feedback and learn |
| `corrections` | Show learned corrections |
| `history` | Show execution history |
| `cleanup` | Remove old plans from database |
| `config` | Show current configuration |

### Organize Workflow

```bash
# Organize entire vault (default)
uv run python -m obsidian-cleanup.cli organize

# Organize specific folder
uv run python -m obsidian-cleanup.cli organize ~/Documents/SecondBrain/00\ -\ Inbox

# Organize without AI (rules only)
uv run python -m obsidian-cleanup.cli organize --no-ai
```

### Interactive Review Keys

During review, press:
- `a` - Approve this plan
- `r` - Reject this plan
- `e` - Edit this plan (change action/target)
- `s` - Skip (leave pending)
- `A` - Approve ALL remaining plans
- `q` - Quit review

### Learning from Corrections

When you revise a plan, the system can learn from your correction:

```bash
# Revise a plan with feedback
uv run python -m obsidian-cleanup.cli revise abc123 "This is a trading note, should go to Finance"

# View learned corrections
uv run python -m obsidian-cleanup.cli corrections
```

The system extracts patterns and keywords from your feedback to improve future classifications.

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `OBSIDIAN_CLEANUP_VAULT_PATH` | Path to Obsidian vault | `~/Documents/SecondBrain` |
| `OBSIDIAN_CLEANUP_DB_PATH` | Database file path | `~/.obsidian-cleanup/plans.db` |
| `OBSIDIAN_CLEANUP_AI_ENABLED` | Enable AI classification | `true` |
| `OBSIDIAN_CLEANUP_AI_CONFIDENCE_THRESHOLD` | Below this, use AI | `0.7` |

### Protected Folders

These folders are never touched:
- `00 - Inbox/` - Intentionally unsorted
- `10 - Meta/` - System/meta notes
- `20 - Journal/` - Daily notes
- `Bookmarks/` - Saved bookmarks
- `52 - Templates/` - Note templates (alternate location)
- `53 - Literature Notes/` - Zettelkasten literature notes
- `54 - Permanent Notes/` - Zettelkasten permanent notes
- `60 - Archives/` - Already archived items
- `90 - Templates/` - Note templates
- `.obsidian/` - Obsidian config
- `.git/` - Git repository

## Frontmatter Support

The tool reads YAML frontmatter for classification hints:

```yaml
---
category: finance
tags: [trading, research]
---
```

### Category Mappings

| Category | Target Area |
|----------|-------------|
| finance, trading, investment | 41 - Finance |
| family, kids, children | 42 - Family |
| work, career, professional | 43 - Work |
| health, medical, fitness | 44 - Health |
| learning, education, course | 45 - Learning |
| projects, project, hobby | 46 - Projects |

## Troubleshooting

### Vault not found

```bash
# Set vault path
export OBSIDIAN_CLEANUP_VAULT_PATH=~/path/to/your/vault

# Then run init
uv run python -m obsidian-cleanup.cli init
```

### AI classification not working

1. Ensure AWS credentials are configured
2. Check Bedrock access in us-west-2 region
3. Run with `--no-ai` to use rules only

### Notes not being classified correctly

1. Add frontmatter category/tags to your notes
2. Use `revise` command to teach the system
3. Check `corrections` to see learned patterns

## Architecture

```
obsidian-cleanup/
├── __init__.py      # Module init
├── config.py        # Settings and paths
├── models.py        # NotePlan, Correction models
├── frontmatter.py   # YAML frontmatter parsing
├── database.py      # SQLite plan storage
├── rules.py         # Rule-based classification
├── classifier.py    # AI classification (Bedrock)
├── executor.py      # File move operations
├── cli.py           # Typer CLI
└── README.md        # This file
```

## Related

- [Filesystem Daemon](../filesystem-daemon/README.md) - Desktop/Downloads organization
- [Obsidian Sync](../obsidian-sync/README.md) - Daily note automation
