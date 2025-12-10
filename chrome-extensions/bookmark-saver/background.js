const BOOKMARK_API_URL = 'https://el5c54bhs2.execute-api.us-east-1.amazonaws.com/bookmarks/save';
const QUEUE_API_URL = 'https://el5c54bhs2.execute-api.us-east-1.amazonaws.com/queue/add';

// Create context menu items on install
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'review-later',
    title: 'Review Later',
    contexts: ['page', 'link'],
  });
  chrome.contextMenus.create({
    id: 'review-later-must',
    title: 'Review Later (Must Review)',
    contexts: ['page', 'link'],
  });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const url = info.linkUrl || info.pageUrl;
  const priority = info.menuItemId === 'review-later-must' ? 'must-review' : 'normal';

  if (!url || url.startsWith('chrome://') || url.startsWith('chrome-extension://')) {
    showNotification('Cannot save', 'Cannot add this to queue');
    return;
  }

  // Show saving badge
  chrome.action.setBadgeText({ text: '...', tabId: tab.id });
  chrome.action.setBadgeBackgroundColor({ color: '#8b5cf6', tabId: tab.id });

  try {
    // Extract metadata from the page
    const [result] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractPageMetadata,
    });

    const metadata = result.result;

    const response = await fetch(QUEUE_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        url: url,
        title: metadata.title,
        meta_description: metadata.description,
        priority: priority,
      }),
    });

    const data = await response.json();

    if (data.success) {
      chrome.action.setBadgeText({ text: '📚', tabId: tab.id });
      chrome.action.setBadgeBackgroundColor({ color: '#8b5cf6', tabId: tab.id });

      let message = data.title;
      message += `\n⏱ ${data.estimated_time} min`;
      if (data.content_type !== 'article') {
        message += ` (${data.content_type})`;
      }
      if (data.is_snack) {
        message += '\n🍿 Quick review!';
      }

      const priorityLabel = priority === 'must-review' ? '🔥 Must Review' : '📚 Review Later';
      showNotification(priorityLabel, message);
    } else {
      throw new Error(data.error || data.detail || 'Failed to add to queue');
    }
  } catch (error) {
    chrome.action.setBadgeText({ text: '✗', tabId: tab.id });
    chrome.action.setBadgeBackgroundColor({ color: '#ef4444', tabId: tab.id });
    showNotification('Error', error.message || 'Failed to add to queue');
    console.error('Queue add error:', error);
  }

  setTimeout(() => {
    chrome.action.setBadgeText({ text: '', tabId: tab.id });
  }, 3000);
});

// Handle extension icon click (bookmark)
chrome.action.onClicked.addListener(async (tab) => {
  if (!tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://')) {
    showNotification('Cannot save', 'Cannot bookmark this page');
    return;
  }

  // Show saving badge
  chrome.action.setBadgeText({ text: '...', tabId: tab.id });
  chrome.action.setBadgeBackgroundColor({ color: '#3b82f6', tabId: tab.id });

  try {
    // Extract metadata from the page (bypasses server-side blocking)
    const [result] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractPageMetadata,
    });

    const metadata = result.result;

    const response = await fetch(BOOKMARK_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        url: tab.url,
        title: metadata.title,
        meta_description: metadata.description,
        mode: 'auto',
      }),
    });

    const data = await response.json();

    if (data.success) {
      // Show success badge
      chrome.action.setBadgeText({ text: '✓', tabId: tab.id });
      chrome.action.setBadgeBackgroundColor({ color: '#10b981', tabId: tab.id });

      // Build notification message
      let message = data.title;

      // Add tags
      if (data.tags && data.tags.length > 0) {
        message += `\n🏷 ${data.tags.slice(0, 3).join(', ')}`;
      }

      showNotification('Bookmark Saved', message);
    } else {
      throw new Error(data.error || data.detail || 'Failed to save');
    }
  } catch (error) {
    // Show error badge
    chrome.action.setBadgeText({ text: '✗', tabId: tab.id });
    chrome.action.setBadgeBackgroundColor({ color: '#ef4444', tabId: tab.id });
    showNotification('Error', error.message || 'Failed to save bookmark');
    console.error('Bookmark save error:', error);
  }

  // Clear badge after 3 seconds
  setTimeout(() => {
    chrome.action.setBadgeText({ text: '', tabId: tab.id });
  }, 3000);
});

// Function injected into the page to extract metadata
function extractPageMetadata() {
  const getMetaContent = (name) => {
    const meta = document.querySelector(`meta[name="${name}"], meta[property="${name}"]`);
    return meta ? meta.getAttribute('content') : null;
  };

  return {
    title: document.title,
    description: getMetaContent('description') || getMetaContent('og:description') || '',
    ogTitle: getMetaContent('og:title'),
    ogImage: getMetaContent('og:image'),
  };
}

function showNotification(title, message) {
  chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icons/icon128.png',
    title: title,
    message: message,
  });
}
