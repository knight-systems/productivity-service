# Obsidian Automation System

> **Phase 3.6 + 3.8 Implementation Plan**
>
> This document describes the architecture and implementation plan for automating Obsidian daily notes with OmniFocus integration, morning briefs, and evening summaries.

## Summary

Build a comprehensive Obsidian automation system that enables:

1. **Webhook/API append** - Append text to daily note from anywhere
2. **OmniFocus → Daily Note** - Auto-inject today's tasks each morning
3. **Morning Brief** - AI-generated summary of calendar + tasks
4. **Evening Summary** - Extract action items from notes → OmniFocus

---

## Key Design Decision: Git-Based Sync

**Problem**: Lambda cannot access iCloud or local filesystems.

**Solution**: Use Git as the sync mechanism:
- Obsidian vault stored in GitHub repo (`toolkmit/second-brain`)
- Lambda pushes changes via GitHub API
- Obsidian Git plugin auto-pulls changes (every 5 min)
- Works across all devices: Personal Mac, Work Mac (no iCloud!), iPhone

**Device Setup**:

| Device | Sync Method |
|--------|-------------|
| Personal Mac | Obsidian Git plugin (auto-pull/push) |
| Work Mac | Obsidian Git plugin (no iCloud needed!) |
| iPhone | Obsidian Git mobile plugin OR Working Copy app |

**Obsidian Git Plugin Configuration**:
- **Auto-pull interval**: Every 5-10 minutes
- **Auto-push**: On save, on interval, or manual only
- **Pull on startup**: Yes (recommended)
- **Commit message**: Auto-generated with timestamp

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AWS (Cloud)                                  │
├─────────────────────────────────────────────────────────────────────┤
│  EventBridge          productivity-service Lambda                    │
│  Scheduler    ───────►  /obsidian/daily/append                      │
│  (6 AM, 8 PM)          /routines/morning-brief                      │
│                        /routines/evening-summary                     │
│                              │                                       │
│                              ▼                                       │
│                        GitHub API ────► toolkmit/second-brain        │
└─────────────────────────────────────────────────────────────────────┘
                                              │
                                    Git pull (5 min)
                                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Local Devices                                     │
├─────────────────────────────────────────────────────────────────────┤
│  Personal Mac          Work Mac              iPhone                  │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐          │
│  │ Obsidian    │      │ Obsidian    │      │ Obsidian    │          │
│  │ Git Plugin  │      │ Git Plugin  │      │ Git Plugin  │          │
│  └─────────────┘      └─────────────┘      └─────────────┘          │
│        │                                                             │
│        ▼                                                             │
│  ┌─────────────┐                                                     │
│  │ launchd     │ ◄── OmniFocus (AppleScript)                        │
│  │ (6 AM cron) │                                                     │
│  └─────────────┘                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Git Vault Setup + Simple Append API

**Goal**: Migrate vault to Git, implement basic append endpoint

**Tasks**:
1. Create `toolkmit/second-brain` repo from existing vault
2. Configure `.gitignore` for Obsidian
3. Set up Obsidian Git plugin on personal Mac
4. Add GitHub PAT to AWS Secrets Manager
5. Implement `github_service.py` in productivity-service
6. Implement `POST /obsidian/daily/append` endpoint
7. Update Lambda IAM policy for Secrets Manager

**Files to Create/Modify**:
```
src/productivity_service/
├── services/
│   ├── github_service.py      # GitHub API operations (NEW)
│   └── obsidian_service.py    # Daily note operations (NEW)
├── routes/
│   └── obsidian.py            # /obsidian/* endpoints (NEW)
├── models/
│   └── daily_note.py          # Request/response models (NEW)
├── main.py                    # Add router (MODIFY)
└── config.py                  # Add env vars (MODIFY)

agent-platform/infra/terraform/
└── main.tf                    # Add secrets (MODIFY)
```

**API Contract**:
```json
POST /obsidian/daily/append
{
  "heading": "Brain Dump",     // Target heading (e.g., "Brain Dump", "Bookmarks")
  "content": "My note text",   // Content to append
  "timestamp": true,           // Optional: prepend HH:MM
  "date": "2025-12-07"         // Optional: specific date (default: today)
}
```

**Success Criteria**: Text appended via API appears in Obsidian within 5 minutes.

---

### Phase 2: Morning Brief + OmniFocus Integration

**Goal**: Auto-populate daily note with tasks and AI-generated brief

**Tasks**:
1. Build local OmniFocus AppleScript extractor
2. Create launchd agent (runs at 6 AM)
3. Implement `POST /routines/morning-brief` endpoint
4. Integrate Google Calendar API (optional)
5. Generate AI summary via Bedrock Haiku

**Files to Create**:
```
obsidian-sync/
├── scripts/
│   ├── extract_omnifocus.applescript  # OmniFocus data extraction
│   └── morning_routine.py             # Orchestration script
├── com.knightsystems.morning-routine.plist  # launchd config
├── install.sh                         # Setup script
└── README.md

src/productivity_service/
├── routes/
│   └── routines.py                    # /routines/* endpoints (NEW)
└── services/
    └── calendar_service.py            # Google Calendar (NEW, optional)
```

**API Contract**:
```json
POST /routines/morning-brief
{
  "tasks": [
    {"title": "Call client", "project": "Work", "due": "2025-12-07", "flagged": true}
  ],
  "include_calendar": true,
  "generate_summary": true
}
```

**Success Criteria**: Wake up to daily note with tasks + AI day preview.

---

### Phase 3: Evening Summary + Action Extraction

**Goal**: Process day's notes, extract action items → OmniFocus

**Tasks**:
1. Implement `POST /routines/evening-summary` endpoint
2. Add EventBridge schedule (8 PM trigger)
3. AI extracts action items from daily note
4. Create OmniFocus tasks via existing Mail Drop flow

**Files to Create/Modify**:
```
src/productivity_service/routes/routines.py  # Add endpoint (MODIFY)

agent-platform/infra/terraform/modules/app-service/
└── main.tf                                  # Add EventBridge (MODIFY)
```

**API Contract**:
```json
POST /routines/evening-summary
{
  "date": "2025-12-07",
  "extract_tasks": true,
  "generate_summary": true
}
```

**Success Criteria**: Action items flow to OmniFocus inbox automatically.

---

### Phase 4: Multi-Device Setup + Polish

**Goal**: Set up all devices, add monitoring

**Tasks**:
1. Set up Obsidian Git on Work Mac
2. Set up Obsidian Git on iPhone
3. Add CloudWatch monitoring
4. Write documentation
5. Add tests

---

## Environment Variables

```bash
# GitHub Integration
OBSIDIAN_VAULT_REPO=toolkmit/second-brain
OBSIDIAN_VAULT_BRANCH=main
GITHUB_PAT_SECRET_ARN=arn:aws:secretsmanager:us-east-1:...

# Google Calendar (optional)
GOOGLE_CALENDAR_ID=primary
GOOGLE_SERVICE_ACCOUNT_SECRET_ARN=arn:aws:secretsmanager:us-east-1:...
```

## Dependencies

Add to `pyproject.toml`:

```toml
PyGithub = "^2.1.0"
google-api-python-client = "^2.100.0"  # Optional for calendar
google-auth = "^2.23.0"                 # Optional for calendar
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Git merge conflicts | Append-only operations, pull before push |
| Sync latency (5 min) | Acceptable for async workflows |
| OmniFocus AppleScript breaks | Abstract in service layer, test on updates |
| Mac offline in morning | Retry mechanism, store last successful date |

---

## Migration Plan (iCloud → Git)

1. **Backup** current vault from iCloud
2. **Create** GitHub repo `toolkmit/second-brain` (private)
3. **Push** vault contents to repo
4. **Clone** repo to local folder (outside iCloud): `~/Documents/SecondBrain`
5. **Point** Obsidian to new location
6. **Install** Obsidian Git plugin, configure auto-pull (5 min)
7. **Test** by making edits, verify sync
8. **Repeat** for Work Mac and iPhone

### Obsidian `.gitignore`

```gitignore
# Obsidian workspace (device-specific)
.obsidian/workspace.json
.obsidian/workspace-mobile.json

# Obsidian cache
.obsidian/cache

# Trash
.trash/

# OS files
.DS_Store
```

---

## Related Documentation

- [Raycast Script Commands](../raycast/README.md) - Mac voice capture
- [Apple Shortcuts](./SHORTCUTS.md) - iOS voice capture
- [Productivity Service API](../README.md) - API documentation
