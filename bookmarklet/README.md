# Bookmark Saver Bookmarklet

A bookmarklet alternative to the Chrome extension that works around Content Security Policy (CSP) restrictions on sites like GitHub.

## How It Works

The bookmarklet:
1. Extracts page metadata (title, description) from the current page
2. Opens a small popup window with the helper page
3. The helper page makes the API call (bypassing CSP since it's on a different domain)
4. Shows success/error feedback and auto-closes

## Setup

### Step 1: Host the Helper Page

You need to make `bookmark-helper.html` accessible via a URL. You have several options:

**Option A: GitHub Pages (Recommended for personal use)**
1. Create a new GitHub repo or use an existing one
2. Upload `bookmark-helper.html` to the repo
3. Enable GitHub Pages in repo settings
4. Your helper page will be at: `https://yourusername.github.io/reponame/bookmark-helper.html`

**Option B: Deploy to AWS S3**
```bash
# Upload to S3 (if you have the AWS CLI configured)
aws s3 cp bookmark-helper.html s3://your-bucket-name/ --acl public-read
```

**Option C: Add to your existing productivity service**
You could add this as a static file served by your Lambda function or host it alongside your service.

### Step 2: Create the Bookmarklet

Once you have the helper page URL, create the bookmarklet:

1. Create a new bookmark in your browser
2. Name it: "💾 Save Bookmark" or "📚 Read Later"
3. For the URL, use this code (replace `HELPER_URL` with your actual URL):

```javascript
javascript:(function(){var m=function(n){var e=document.querySelector('meta[name="'+n+'"],meta[property="'+n+'"]');return e?e.getAttribute('content'):''};var t=document.title;var d=m('description')||m('og:description')||'';var u=encodeURIComponent(window.location.href);var et=encodeURIComponent(t);var ed=encodeURIComponent(d);var w=window.open('HELPER_URL?url='+u+'&title='+et+'&description='+ed,'bookmark','width=450,height=550,scrollbars=no,resizable=no');})();
```

**Example with GitHub Pages:**
```javascript
javascript:(function(){var m=function(n){var e=document.querySelector('meta[name="'+n+'"],meta[property="'+n+'"]');return e?e.getAttribute('content'):''};var t=document.title;var d=m('description')||m('og:description')||'';var u=encodeURIComponent(window.location.href);var et=encodeURIComponent(t);var ed=encodeURIComponent(d);var w=window.open('https://yourusername.github.io/bookmark-helper/bookmark-helper.html?url='+u+'&title='+et+'&description='+ed,'bookmark','width=450,height=550,scrollbars=no,resizable=no');})();
```

### Step 3: Use It

1. Navigate to any webpage you want to save
2. Click the bookmarklet in your bookmarks bar
3. A popup will open showing mode selection (Bookmark, Read Later, Must Read)
4. It will auto-save after 1 second (or click a mode to change before it saves)
5. The popup will show success/error and auto-close

## Formatted Bookmarklet Code

Here's the same code formatted for readability (minified version above is what you use):

```javascript
javascript:(function() {
  // Extract metadata
  var getMeta = function(name) {
    var el = document.querySelector('meta[name="' + name + '"],meta[property="' + name + '"]');
    return el ? el.getAttribute('content') : '';
  };

  var title = document.title;
  var description = getMeta('description') || getMeta('og:description') || '';
  var url = encodeURIComponent(window.location.href);
  var encodedTitle = encodeURIComponent(title);
  var encodedDesc = encodeURIComponent(description);

  // Open popup with helper page
  var popup = window.open(
    'HELPER_URL?url=' + url + '&title=' + encodedTitle + '&description=' + encodedDesc,
    'bookmark',
    'width=450,height=550,scrollbars=no,resizable=no'
  );
})();
```

## Features

- **Mode Selection**: Choose between Bookmark, Read Later, or Must Read
- **Auto-save**: Saves after 1 second (you can click a different mode before that)
- **Visual Feedback**: Shows loading state, success with tags/time, or error messages
- **Auto-close**: Popup closes automatically after success
- **CSP Bypass**: Works on sites like GitHub that block inline scripts
- **No Extension Required**: Pure JavaScript, works in any browser

## Troublading

### Popup is Blocked
- Allow popups for the site you're bookmarking
- Some browsers require user interaction before opening popups
- The bookmarklet will only work when clicking it manually (not from console)

### Helper Page Not Loading
- Make sure the helper page URL is correct and accessible
- Check browser console for errors
- Verify CORS isn't blocking the page (shouldn't be an issue with public hosting)

### API Errors
- Check that the API endpoints in `bookmark-helper.html` are correct
- Verify your Lambda functions are deployed and accessible
- Check the browser console in the popup window for API error details

## Customization

### Change Auto-save Delay
Edit line in `bookmark-helper.html`:
```javascript
setTimeout(save, 1000); // Change 1000 to desired milliseconds
```

### Change Default Mode
Edit line in `bookmark-helper.html`:
```javascript
let selectedMode = 'bookmark'; // Change to 'read-later' or 'must-read'
```

### Change Popup Size
Edit the bookmarklet code:
```javascript
'width=450,height=550,...' // Adjust dimensions
```

## Advantages Over Extension

- ✅ Works in any browser (Safari, Firefox, Chrome, Edge, etc.)
- ✅ No installation or permissions required
- ✅ Bypasses CSP restrictions
- ✅ Easy to update (just change the helper page)
- ✅ Can be used at work where extensions are restricted

## Disadvantages

- ❌ Requires hosting the helper page somewhere
- ❌ Opens a popup (vs. seamless background save)
- ❌ No right-click context menu
- ❌ Popup blockers may interfere
