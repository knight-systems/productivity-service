# Obsidian Sync - Morning Routine

Local automation scripts for OmniFocus → Obsidian daily note integration.

## What It Does

**Morning Routine (6 AM daily)**
1. Extracts flagged/due tasks from OmniFocus via AppleScript
2. Calls `/routines/morning-brief` API
3. AI generates a summary of your day
4. Tasks + summary injected into daily note

## Installation

```bash
./install.sh
```

This:
- Creates log directory at `~/.local/log/morning-routine/`
- Installs the launchd agent to run at 6 AM daily
- Installs required Python dependencies

## Manual Testing

```bash
# Test OmniFocus extraction
osascript scripts/extract_omnifocus.applescript | python3 -m json.tool

# Test full morning routine
python3 scripts/morning_routine.py
```

## Logs

```bash
# View routine logs
tail -f ~/.local/log/morning-routine/morning_routine.log

# View launchd output
tail -f ~/.local/log/morning-routine/launchd.log
```

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.knightsystems.morning-routine.plist
rm ~/Library/LaunchAgents/com.knightsystems.morning-routine.plist
```

## Files

| File | Purpose |
|------|---------|
| `scripts/extract_omnifocus.applescript` | Extracts tasks from OmniFocus |
| `scripts/morning_routine.py` | Orchestration script |
| `com.knightsystems.morning-routine.plist` | launchd agent config |
| `install.sh` | Installation script |

## Troubleshooting

**OmniFocus extraction fails**
- Ensure OmniFocus is installed and has tasks
- Grant Terminal/script automation permissions in System Settings

**API calls fail**
- Check internet connection
- Verify API is running: `curl https://el5c54bhs2.execute-api.us-east-1.amazonaws.com/health`

**launchd doesn't run**
- Check agent is loaded: `launchctl list | grep morning`
- Check logs for errors
- Ensure Mac is awake at 6 AM (won't run if sleeping)
