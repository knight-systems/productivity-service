const API_URL = 'https://el5c54bhs2.execute-api.us-east-1.amazonaws.com/bookmarks/save';

// Handle extension icon click
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

    const response = await fetch(API_URL, {
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

      // Show notification with tags
      const tagsText = data.tags && data.tags.length > 0
        ? `\nTags: ${data.tags.join(', ')}`
        : '';
      showNotification('Bookmark Saved', `${data.title}${tagsText}`);
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
