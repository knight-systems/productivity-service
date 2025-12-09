# Filesystem Daemon

AI-powered file organization for Desktop and Downloads. Classifies files using rules and Claude AI, then moves them to organized folders based on life domains.

## Quick Start

```bash
# From productivity-service root
cd ~/Dropbox/web-projects/productivity-service

# Initialize database and directories
uv run python -m filesystem-daemon.cli init

# Organize your Desktop (interactive workflow)
uv run python -m filesystem-daemon.cli organize ~/Desktop
```

## The `organize` Command (Recommended)

The primary way to use this tool is the interactive `organize` command:

```bash
uv run python -m filesystem-daemon.cli organize ~/Desktop
uv run python -m filesystem-daemon.cli organize ~/Downloads
```

### Workflow Steps

1. **Scan** - Classifies all files using rules first, then AI for uncertain files
2. **Auto-approve deletes** - Screenshots and installers are auto-approved for deletion
3. **Interactive review** - Review non-delete items with keyboard shortcuts:
   - `a` - Approve (keep current action)
   - `d` - Change to DELETE
   - `s` - Skip/reject (leave file alone)
   - `m` - Move to different domain/subfolder
   - `n` - Next (skip without changing)
   - `q` - Quit review
4. **Summary** - Shows counts by action type
5. **Execute menu**:
   - `e` - Execute all approved plans
   - `r` - Re-review all items
   - `d` - Review only deletes
   - `m` - Review only moves
   - `s` - Rescan directory
   - `q` - Quit without executing

## Life Domains

Files are organized into these top-level folders under `~/Areas/`:

| Domain | Description | Example Files |
|--------|-------------|---------------|
| **Finance** | Banking, taxes, trading | statements, 1099s, trading research |
| **Health** | Medical records | prescriptions, lab results, BP logs |
| **Work** | Career, learning | resumes, courses, ebooks |
| **Property** | Home ownership | mortgage docs, HOA, deeds |
| **Family** | Family documents | birth certs, passports, school reports |
| **Personal** | Everything else | receipts, screenshots, media |

Each domain has subfolders: `Documents/`, `Media/`, `Research/`, `Projects/`, `Archive/`

## Classification System

### Rule-Based Classification

Files are first matched against rules in `rules.py`:

```python
# High confidence (auto-action)
- Screenshots → DELETE (95%)
- .dmg/.pkg installers → DELETE (95%)
- .tmp/.crdownload → DELETE (95%)

# Medium confidence
- Tax documents → Finance/Documents (85%)
- Trading research → Finance/Research (85%)
- Health documents → Health/Documents (90%)

# Low confidence (needs AI)
- Generic PDFs → Unknown (50%)
- Images → Personal/Media (60%)
```

### AI Classification

Files below the confidence threshold (default 0.7) are sent to Claude AI for classification. The AI:

1. Analyzes filename patterns
2. Extracts PDF metadata when available
3. Suggests appropriate domain and subfolder
4. Generates standardized rename: `YYYY-MM-DD-description.ext`

### Learned Corrections

When you revise a classification, the system learns from your feedback:

```bash
uv run python -m filesystem-daemon.cli revise abc123 "this is a health document"
```

Future similar files will use your correction automatically.

## File Renaming

Files are renamed to a standardized format:

```
Original: IMG_4521.jpg
Renamed:  2024-03-15-vacation-beach-photo.jpg

Original: Document (1).pdf
Renamed:  2024-12-01-chase-bank-statement.pdf
```

The date is extracted from:
1. Filename patterns (e.g., `Screenshot 2024-03-15`)
2. PDF metadata (creation date)
3. File modification time (fallback)

## CLI Commands Reference

### Primary Commands

| Command | Description |
|---------|-------------|
| `organize [PATH]` | **Recommended** - Full interactive workflow (scan, review, execute) |
| `init` | Initialize database and create directories |
| `config` | Show current configuration |

### Plan Management

| Command | Description |
|---------|-------------|
| `pending` | Show all pending plans |
| `show ID` | Show details of a specific plan |
| `review` | Interactive review of pending plans (standalone) |
| `history` | Show executed/rejected plans |
| `cleanup` | Remove old plans from database |

### Advanced Commands

| Command | Description |
|---------|-------------|
| `revise ID "feedback"` | Revise plan with natural language feedback |
| `corrections` | Show learned corrections from past feedback |
| `watch` | Start file watcher daemon (background mode) |

## Configuration

Configuration is in `config.py`. Key settings:

```python
# Paths
watch_paths = ["~/Desktop", "~/Downloads"]
areas_path = "~/Areas"

# AI Settings
ai_enabled = True
ai_confidence_threshold = 0.7
max_file_size_for_ai_mb = 10

# Behavior
dry_run = False
backup_before_move = True
ignore_hidden = True
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FILE_CLASSIFIER_DB` | Database path | `~/.file-classifier/classifier.db` |
| `FILE_CLASSIFIER_AREAS` | Areas folder | `~/Areas` |
| `AWS_PROFILE` | AWS profile for Bedrock | default |

## Database

Plans are stored in SQLite at `~/.file-classifier/plans.db`:

```sql
-- Plan statuses
pending    -- Awaiting review
approved   -- Ready to execute
executed   -- Action completed
rejected   -- User rejected
failed     -- Execution failed
revised    -- Replaced by new plan
```

## Running as a Daemon

For automatic file watching (optional):

```bash
# Install launchd service
./filesystem-daemon/install.sh

# Check status
launchctl list | grep file-classifier

# View logs
tail -f ~/.file-classifier/logs/stdout.log
```

The daemon watches Desktop and Downloads, creating plans for new files automatically.

## Raycast Integration

A Raycast script command is available:

```bash
# In Raycast, search for "Organize Files"
# Opens terminal with the organize workflow
```

See `raycast/README.md` for setup instructions.

## Examples

### Organize Desktop

```bash
uv run python -m filesystem-daemon.cli organize ~/Desktop
```

### Organize Downloads

```bash
uv run python -m filesystem-daemon.cli organize ~/Downloads
```

### Review existing plans (without rescanning)

```bash
# View pending plans
uv run python -m filesystem-daemon.cli pending

# Interactive review
uv run python -m filesystem-daemon.cli review
```

### Check details of a specific plan

```bash
uv run python -m filesystem-daemon.cli show PLAN_ID
```

### Revise a plan with feedback

```bash
uv run python -m filesystem-daemon.cli revise PLAN_ID "this is a health document, move to Health"
```

## Troubleshooting

### Files not being renamed

Ensure the AI prompt is returning `suggested_name`. Check with:

```bash
uv run python -m filesystem-daemon.cli show PLAN_ID
```

### Screenshots not detected

macOS uses special Unicode characters in screenshot names. The rules handle:
- Regular space (U+0020)
- Non-breaking space (U+00A0)
- Narrow no-break space (U+202F)

### Database errors

Reset the database:

```bash
rm ~/.file-classifier/plans.db
uv run python -m filesystem-daemon.cli init
```

### AI classification fails

Check AWS credentials and Bedrock access:

```bash
aws bedrock-runtime invoke-model --model-id anthropic.claude-3-haiku-20240307-v1:0 ...
```
