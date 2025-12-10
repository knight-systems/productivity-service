# Quick Start - 2 Minutes to Working Bookmarklet

## 1. Copy the Bookmarklet Code

Open `bookmarklet-code.txt` and copy its contents, or copy this directly to your clipboard:

```bash
cat bookmarklet-code.txt | pbcopy
```

## 2. Add to Browser

1. Show your bookmarks bar (**Cmd+Shift+B** on Mac)
2. Right-click the bookmarks bar → **Add Page** or **New Bookmark**
3. Name: `💾 Save`
4. URL: Paste the code you copied
5. Save

## 3. Done!

Click the bookmarklet on any page. A popup will open with 4 modes:

| Mode | What it does |
|------|--------------|
| **📑 Bookmark** | Save with AI-generated tags |
| **📚 Review Later** | Add to review queue (normal priority) |
| **🔥 Must Review** | Add to queue → creates OmniFocus task |
| **✓ Reviewed** | Mark current page as consumed |

Auto-saves after 1 second. Click a different mode to change before it saves.

---

## Troubleshooting

### Popup Blocked?
Click "Always allow popups" for the site you're on.

### Nothing Happens?
Open browser console (F12) and check for JavaScript errors. Make sure the bookmarklet code copied correctly without extra spaces or line breaks.

### Helper Page Not Loading?
Try accessing directly: https://knight-systems.github.io/bookmark-helper/

### API Error?
Check the console in the popup window for detailed error messages.
