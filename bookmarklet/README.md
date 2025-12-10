# Bookmark Saver Bookmarklet

A bookmarklet alternative to the Chrome extension that works around Content Security Policy (CSP) restrictions on sites like GitHub.

## Quick Setup (Using Hosted Helper)

The helper page is already hosted at: **https://knight-systems.github.io/bookmark-helper/**

### 1. Copy the Bookmarklet Code

Copy the contents of `bookmarklet-code.txt` or use this:

```javascript
javascript:(function(){var m=function(n){var e=document.querySelector('meta[name="'+n+'"],meta[property="'+n+'"]');return e?e.getAttribute('content'):''};var t=document.title;var d=m('description')||m('og:description')||'';var u=encodeURIComponent(window.location.href);var et=encodeURIComponent(t);var ed=encodeURIComponent(d);window.open('https://knight-systems.github.io/bookmark-helper/?url='+u+'&title='+et+'&description='+ed,'bookmark','width=450,height=550');})();
```

### 2. Add to Browser

1. Show your bookmarks bar (Cmd+Shift+B on Mac, Ctrl+Shift+B on Windows)
2. Right-click the bookmarks bar → Add Page / New Bookmark
3. Name: `💾 Save` (or whatever you like)
4. URL: Paste the javascript code from step 1
5. Save

### 3. Use It

1. Navigate to any webpage
2. Click the bookmarklet
3. A popup opens with 4 mode buttons:
   - **📑 Bookmark** - Save with AI-generated tags
   - **📚 Review Later** - Add to review queue (normal priority)
   - **🔥 Must Review** - Add to queue (high priority) → creates OmniFocus task
   - **✓ Reviewed** - Mark current page as consumed
4. Auto-saves after 1 second (or click a different mode first)
5. Popup auto-closes after success

---

## How It Works

The bookmarklet:
1. Extracts page metadata (title, description) from the current page
2. Opens a small popup window with the helper page
3. The helper page makes the API call (bypassing CSP since it's on a different domain)
4. Shows success/error feedback and auto-closes

---

## Self-Hosting the Helper Page

If you want to host your own copy of the helper page:

### Option A: GitHub Pages

1. Create a new GitHub repo (e.g., `bookmark-helper`)
2. Copy `bookmark-helper.html` as `index.html`
3. Add the GitHub Pages workflow (see `.github/workflows/pages.yml` in the bookmark-helper repo)
4. Push to main branch
5. Your page will be at: `https://YOUR_USERNAME.github.io/bookmark-helper/`

### Option B: AWS S3

```bash
aws s3 cp bookmark-helper.html s3://your-bucket-name/ \
  --acl public-read \
  --content-type "text/html; charset=utf-8"
```

Then update the bookmarklet URL to point to your hosted version.

---

## Features

- **Mode Selection**: Choose between Bookmark, Review Later, Must Review, or Mark Reviewed
- **Auto-save**: Saves after 1 second (you can click a different mode before that)
- **Visual Feedback**: Shows loading state, success with tags/time, or error messages
- **Auto-close**: Popup closes automatically after success
- **CSP Bypass**: Works on sites like GitHub that block inline scripts
- **No Extension Required**: Pure JavaScript, works in any browser

---

## Troubleshooting

### Popup is Blocked
- Allow popups for the site you're bookmarking
- Some browsers require user interaction before opening popups
- The bookmarklet will only work when clicking it manually (not from console)

### Helper Page Not Loading
- Make sure the helper page URL is correct and accessible
- Check browser console for errors
- Try accessing the helper page directly: https://knight-systems.github.io/bookmark-helper/

### API Errors
- Check the browser console in the popup window for API error details
- Verify your Lambda functions are deployed and accessible

---

## Customization

### Change Auto-save Delay
Edit line in `bookmark-helper.html`:
```javascript
setTimeout(save, 1000); // Change 1000 to desired milliseconds
```

### Change Default Mode
Edit line in `bookmark-helper.html`:
```javascript
let selectedMode = 'bookmark'; // Change to 'review-later', 'must-review', or 'mark-reviewed'
```

---

## Advantages Over Extension

- Works in any browser (Safari, Firefox, Chrome, Edge, etc.)
- No installation or permissions required
- Bypasses CSP restrictions
- Easy to update (just change the helper page)
- Can be used at work where extensions are restricted

## Disadvantages

- Opens a popup (vs. seamless background save)
- No right-click context menu
- Popup blockers may interfere
