# Quick Start - 5 Minutes to Working Bookmarklet

## Option 1: GitHub Pages (Easiest)

### 1. Upload Helper Page to GitHub
```bash
# Create a new public repo on GitHub called "bookmark-helper"
# Clone it locally
git clone https://github.com/YOUR_USERNAME/bookmark-helper.git
cd bookmark-helper

# Copy the helper file
cp /path/to/bookmark-helper.html index.html

# Commit and push
git add index.html
git commit -m "Add bookmark helper"
git push
```

### 2. Enable GitHub Pages
1. Go to your repo settings
2. Click "Pages" in the left sidebar
3. Under "Source", select "main" branch
4. Click "Save"
5. Your page will be at: `https://YOUR_USERNAME.github.io/bookmark-helper/`

### 3. Create Bookmarklet

**Copy this ENTIRE line** (replace YOUR_USERNAME):

```javascript
javascript:(function(){var m=function(n){var e=document.querySelector('meta[name="'+n+'"],meta[property="'+n+'"]');return e?e.getAttribute('content'):''};var t=document.title;var d=m('description')||m('og:description')||'';var u=encodeURIComponent(window.location.href);var et=encodeURIComponent(t);var ed=encodeURIComponent(d);window.open('https://YOUR_USERNAME.github.io/bookmark-helper/?url='+u+'&title='+et+'&description='+ed,'bookmark','width=450,height=550');})();
```

### 4. Add to Browser
1. Show your bookmarks bar (Ctrl+Shift+B or Cmd+Shift+B)
2. Right-click the bookmarks bar → Add Page / New Bookmark
3. Name: `💾 Save` (or whatever you like)
4. URL: Paste the javascript code from step 3
5. Save

### 5. Done!
Click the bookmarklet on any page to save it.

---

## Option 2: AWS S3 (If you're already using AWS)

### 1. Upload to S3
```bash
cd /path/to/productivity-service/bookmarklet

# Create bucket or use existing one
aws s3 mb s3://my-bookmarklet-helper

# Upload file with public read access
aws s3 cp bookmark-helper.html s3://my-bookmarklet-helper/ \
  --acl public-read \
  --content-type "text/html; charset=utf-8"

# Your URL will be:
# https://my-bookmarklet-helper.s3.amazonaws.com/bookmark-helper.html
```

### 2. Create Bookmarklet
Use the same javascript code as Option 1, but replace the URL with your S3 URL.

---

## Option 3: Local File (Testing Only)

For testing, you can use a `file://` URL, but it won't work on all websites:

```javascript
javascript:(function(){var m=function(n){var e=document.querySelector('meta[name="'+n+'"],meta[property="'+n+'"]');return e?e.getAttribute('content'):''};var t=document.title;var d=m('description')||m('og:description')||'';var u=encodeURIComponent(window.location.href);var et=encodeURIComponent(t);var ed=encodeURIComponent(d);window.open('file:///Users/marc.knight/code/productivity-service/bookmarklet/bookmark-helper.html?url='+u+'&title='+et+'&description='+ed,'bookmark','width=450,height=550');})();
```

⚠️ **Note**: `file://` URLs have security restrictions and won't work on many sites. Use GitHub Pages or S3 for production use.

---

## Testing

1. Navigate to any article (try this README on GitHub!)
2. Click your bookmarklet
3. A popup should open showing:
   - Mode selection (Bookmark / Review Later / Must Review)
   - Loading indicator
   - Success message with tags (or error if something went wrong)
4. Popup auto-closes after success

---

## Troubleshooting

### Popup Blocked?
- Click "Always allow popups" for the site you're on
- Try clicking the bookmarklet again

### Nothing Happens?
- Open browser console (F12)
- Check for JavaScript errors
- Make sure the bookmarklet code copied correctly

### Helper Page Not Loading?
- Check if GitHub Pages is enabled (takes 1-2 minutes after enabling)
- Try accessing the helper page directly in a new tab
- Check that the URL in your bookmarklet matches your GitHub Pages URL

### API Error?
- The APIs should be working (same as your Chrome extension)
- Check the console in the popup window for detailed error messages
- Verify you're not on a `chrome://` or `about:` page

---

## Using Different Modes

The popup offers 3 modes:

1. **📑 Bookmark** - Saves immediately with AI-generated tags
2. **📚 Review Later** - Adds to your review queue (normal priority)
3. **🔥 Must Review** - Adds to queue with high priority

Default is Bookmark. You have 1 second to click a different mode before it auto-saves.

To change the default mode, edit `bookmark-helper.html` line 122:
```javascript
let selectedMode = 'review-later'; // or 'must-review'
```
