# Review Queue System

A system for saving links/resources to consume later, separate from bookmarking (which is for content you've already reviewed).

## Overview

- **Bookmarks** (`/bookmarks/save`) = Content you've already consumed, saved for reference
- **Review Queue** (`/queue/add`) = Content you want to consume later

## V1 Implementation (Current)

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/queue/add` | Add item to review queue |
| PATCH | `/queue/{id}/consume` | Mark item as consumed |
| PATCH | `/queue/{id}/status` | Update queue status |

#### POST /queue/add

Adds a URL to the review queue with automatic content detection.

**Request:**
```json
{
  "url": "https://example.com/article",
  "title": "Optional title override",
  "meta_description": "Optional description",
  "priority": "normal",
  "notes": "Optional notes"
}
```

**Priority values:** `must-review`, `normal`, `someday`, `snack` (auto-detected)

**Response:**
```json
{
  "success": true,
  "queue_id": "2025-12-10-article-title",
  "title": "Article Title",
  "url": "https://example.com/article",
  "content_type": "article",
  "estimated_time": 5,
  "priority": "normal",
  "is_snack": false
}
```

#### PATCH /queue/{id}/consume

Marks a queue item as consumed.

**Request (optional):**
```json
{
  "notes": "Key takeaways from reviewing"
}
```

#### PATCH /queue/{id}/status

Updates queue status without marking as consumed.

**Request:**
```json
{
  "status": "reviewing"
}
```

**Status values:** `unreviewed`, `reviewing`, `consumed`, `archived`

### Content Type Detection

Automatically detected from URL patterns:

| Content Type | URL Patterns |
|--------------|--------------|
| video | youtube.com, youtu.be, vimeo.com, twitch.tv |
| tweet | twitter.com/*/status, x.com/*/status |
| pdf | *.pdf |
| doc | docs.google.com, notion.so |
| podcast | podcasts.apple.com, spotify.com/episode, overcast.fm |
| article | Default for everything else |

### Time Estimation

| Content Type | Default Time |
|--------------|--------------|
| tweet | 1 min |
| article | 5 min (or word count / 200) |
| video | 10 min |
| pdf | 10 min |
| doc | 5 min |
| podcast | 30 min |

### Snack Detection

Content estimated at 2 minutes or less is automatically marked as a "snack" - quick reviews perfect for small pockets of downtime.

### Storage

Queue items are stored in `ReviewQueue/` folder in Obsidian vault with frontmatter:

```yaml
---
title: "Article Title"
url: https://example.com
created: 2025-12-10
content_type: article
estimated_time: 5
queue_status: unreviewed
priority: normal
added_to_queue: 2025-12-10
last_touched: 2025-12-10
consumed_at:
---
```

### Chrome Extension

The extension now has two actions:

1. **Click icon** = Save as bookmark (for content you've reviewed)
2. **Right-click menu**:
   - "Review Later" = Add to queue (normal priority)
   - "Review Later (Must Review)" = Add to queue (must-review priority)

Works on both the current page and links you right-click on.

### Obsidian Dataview Template

Copy `obsidian-templates/Review Queue.md` to your vault to get a queue dashboard with sections:

- Must Review
- Snacks (< 2 min)
- Up Next
- Someday
- Currently Reviewing
- Recently Consumed
- Queue Stats

---

## Future Phases

### Phase 2: Priority Decay & Queue API

**Priority decay automation:**
- `must-review` → `normal` after 7 days untouched
- `normal` → `someday` after 14 days untouched
- Implemented on-read (lazy evaluation when queue is fetched)

**New endpoints:**
```
GET /queue
  - List queue items with filtering
  - ?status=unreviewed&priority=must-review&limit=10
```

**Raycast commands:**
- Add to Review Queue command
- View queue command

### Phase 3: Smart Suggest

**New endpoint:**
```
POST /queue/suggest
  - AI picks best item based on context
  - Input: available_time (minutes), device (mobile/desktop)
  - Returns: recommended item with reasoning
```

**Example:**
```json
{
  "available_time": 5,
  "device": "mobile",
  "context": "commute"
}
```

Response:
```json
{
  "queue_id": "2025-12-10-quick-article",
  "title": "Quick Article",
  "reason": "5-min article, perfect for your commute"
}
```

### Phase 4: Mobile & Consumption Flow

**iOS Shortcuts:**
- Share sheet "Add to Review Queue"
- "What to Review" shortcut (calls /queue/suggest)
- Quick "Mark Consumed" action

**Consumption notes flow:**
- Quick content (< 5 min): Archive silently
- Long content (> 10 min): Prompt for notes/takeaways

### Phase 5: Polish

**DynamoDB caching:**
- Cache queue state for fast filtering
- Sync to Obsidian files

**Statistics/insights:**
- Review velocity
- Content type breakdown
- Queue growth trends

**Queue cleanup automation:**
- Auto-archive stale items
- Weekly digest of forgotten items

---

## Files Modified (V1)

### New Files
- `src/productivity_service/routes/queue.py` - Queue API endpoints
- `obsidian-templates/Review Queue.md` - Dataview template

### Modified Files
- `src/productivity_service/main.py` - Added queue router
- `src/productivity_service/models/bookmark.py` - Added QueueStatus, QueuePriority, ContentType enums
- `src/productivity_service/services/bookmark_service.py` - Added content type detection (for bookmark response)
- `chrome-extensions/bookmark-saver/background.js` - Added context menu for Review Later
- `chrome-extensions/bookmark-saver/manifest.json` - Added contextMenus permission
