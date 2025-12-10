# OmniFocus Integration + Read → Review Renaming

## Goals
1. When items are marked as "must-review" priority, create an OmniFocus task instead of saving to Obsidian ReviewQueue
2. Comprehensively rename all "read" terminology to "review" (folder names, variables, UI text, enums, documentation)

## User Requirements
- **Must-review items** → OmniFocus task with format: `Review: {title} [{type}]`
- **Regular queue items** → Obsidian ReviewQueue (existing behavior)
- URL in task note for easy access
- Graceful fallback if OmniFocus fails
- All user-facing text uses "review" terminology (Chrome extension, bookmarklet, Obsidian templates)
- Internal code uses "review" terminology (enums, variables, constants)

## Implementation Strategy

Execute in **two phases**:
1. **Phase 1**: Comprehensive read → review renaming (foundation)
2. **Phase 2**: OmniFocus integration (builds on renamed code)

This order prevents having to rename code twice (once before OmniFocus, once after).

---

## PHASE 1: Read → Review Renaming

### Step 1.1: Update Python Enums and Models
**File**: `src/productivity_service/models/queue.py`

Changes:
- Line 1: Docstring `"read queue"` → `"review queue"`
- Line 9: `UNREAD = "unread"` → `UNREVIEWED = "unreviewed"`
- Line 10: `READING = "reading"` → `REVIEWING = "reviewing"`
- Line 18: `MUST_READ = "must-read"` → `MUST_REVIEW = "must-review"`

### Step 1.2: Update Python Backend Routes
**File**: `src/productivity_service/routes/queue.py`

Changes:
- Line 1: Docstring `"read queue"` → `"review queue"`
- Line 23: `QUEUE_FOLDER = "ReadQueue"` → `"ReviewQueue"`
- Line 55: `DEFAULT_READ_TIMES` → `DEFAULT_REVIEW_TIMES`
- Line 54: Comment `"reading times"` → `"review times"`
- Line 91: Docstring `"read queue"` → `"review queue"`
- Line 123: Function name `_estimate_read_time` → `_estimate_review_time`
- Line 124: Docstring `"reading time"` → `"review time"`
- Line 162: Frontmatter default `"queue_status: unread"` → `"unreviewed"`
- Line 250: Docstring `"read queue"` → `"review queue"`
- Line 252-253: Comments update
- Line 282: Variable `estimated_time = _estimate_read_time(...)` → `_estimate_review_time(...)`
- Line 310: Commit message `"read queue"` → `"review queue"`
- Line 428: Comment `'reading'` → `'reviewing'`

### Step 1.3: Update Chrome Extension
**File**: `chrome-extensions/bookmark-saver/background.js`

Changes:
- Line 7: `id: 'read-later'` → `'review-later'`
- Line 8: `title: 'Read Later'` → `'Review Later'`
- Line 12: `id: 'read-later-must'` → `'review-later-must'`
- Line 13: `title: 'Read Later (Must Read)'` → `'Review Later (Must Review)'`
- Line 21: `'read-later-must' ? 'must-read'` → `'review-later-must' ? 'must-review'`
- Line 69: `'must-read' ? '🔥 Must Read' : '📚 Read Later'` → `'must-review' ? '🔥 Must Review' : '📚 Review Later'`

### Step 1.4: Update Bookmarklet
**File**: `bookmarklet/bookmark-helper.html`

Changes:
- Line 133: `data-mode="read-later">📚 Read Later` → `"review-later">📚 Review Later`
- Line 134: `data-mode="must-read">🔥 Must Read` → `"must-review">🔥 Must Review`
- Line 198: Comment `"Add to read queue"` → `"review queue"`
- Line 199: `'must-read' ? 'must-read'` → `'must-review' ? 'must-review'`
- Line 225: `'must-read'` → `'must-review'`
- Line 227: `'Added to Must Read!' : 'Added to Read Later!'` → `'Must Review!' : 'Review Later!'`
- Line 240: `min read` → `min review`

### Step 1.5: Update Bookmarklet Documentation
**Files**:
- `bookmarklet/README.md` - Line 123: `'read-later' or 'must-read'` → `'review-later' or 'must-review'`
- `bookmarklet/QUICK_START.md` - Line 123: Update text, Line 130: Update mode names

### Step 1.6: Rename and Update Documentation Files

**Rename files**:
- `docs/READ_QUEUE.md` → `docs/REVIEW_QUEUE.md`
- `obsidian-templates/Reading Queue.md` → `obsidian-templates/Review Queue.md`

**Update** `docs/REVIEW_QUEUE.md` (30+ occurrences):
- Title: `Read Queue System` → `Review Queue System`
- All instances of "read queue" → "review queue"
- All instances of "must-read" → "must-review"
- All instances of "unread" → "unreviewed"
- All instances of "reading" → "reviewing"
- All instances of "ReadQueue/" → "ReviewQueue/"
- Endpoint descriptions updated
- Chrome extension menu items updated
- All priority values updated

**Update** `obsidian-templates/Review Queue.md` (20+ occurrences):
- Title: `📚 Reading Queue` → `📚 Review Queue`
- Section: `Must Read` → `Must Review`
- Section: `Currently Reading` → `Currently Reviewing`
- All Dataview WHERE clauses: `"unread"` → `"unreviewed"`, `"reading"` → `"reviewing"`, `"must-read"` → `"must-review"`
- All FROM clauses: `"ReadQueue"` → `"ReviewQueue"` (7 times)

---

## PHASE 2: OmniFocus Integration

### Step 2.1: Add Helper Function for Content Type Display
**File**: `src/productivity_service/routes/queue.py`
**Location**: After `_estimate_review_time` (around line 131)

```python
def _format_content_type_display(content_type: ContentType) -> str:
    """Format content type for display in task titles."""
    if content_type == ContentType.DOC:
        return "gdoc"
    return content_type.value
```

### Step 2.2: Add Must-Review Handler Function
**File**: `src/productivity_service/routes/queue.py`
**Location**: After helper functions (around line 140)

```python
async def _handle_must_review_item(
    title: str,
    url: str,
    content_type: ContentType,
    estimated_time: int,
    priority: QueuePriority,
    is_snack: bool,
    queue_id: str,
) -> QueueAddResponse:
    """Handle must-review items by creating OmniFocus task."""
```

**Logic**:
1. Format task title: `Review: {title} [{type}]`
2. Create `TaskCreateRequest(title=formatted_title, note=url)`
3. Call `create_omnifocus_task()`
4. If success: Return response with `omnifocus_task_created=True`
5. If failure: **Fallback to Obsidian** (graceful degradation)
   - Log warning
   - Create markdown file in ReviewQueue
   - Return response with `error` field explaining fallback

### Step 2.3: Add Imports
**File**: `src/productivity_service/routes/queue.py`
**Location**: Top of file (around line 16)

```python
from ..services.omnifocus import create_omnifocus_task
from ..models.task import TaskCreateRequest
```

### Step 2.4: Modify add_to_queue Function
**File**: `src/productivity_service/routes/queue.py`
**Location**: Lines 248-337

**Change**: After computing metadata (after line 286), add priority check:

```python
# Generate ID (needed for both paths)
queue_id = _generate_queue_id(title, date_str)

# Branch based on priority
if priority == QueuePriority.MUST_REVIEW:
    return await _handle_must_review_item(
        title=title,
        url=url,
        content_type=content_type,
        estimated_time=estimated_time,
        priority=priority,
        is_snack=is_snack,
        queue_id=queue_id,
    )

# Continue with existing Obsidian flow for non-must-review items
queue_path = f"{QUEUE_FOLDER}/{queue_id}.md"
# ... rest of existing code
```

### Step 2.5: Update Response Model
**File**: `src/productivity_service/routes/queue.py`
**Location**: Lines 100-111

Add optional field to `QueueAddResponse`:

```python
omnifocus_task_created: bool = False
```

Indicates whether OmniFocus task was created (vs Obsidian file).

---

## Task Format Examples
- Article: `Review: Architecture Guide [article]`
- Google Doc: `Review: Q4 Meeting Notes [gdoc]`
- Video: `Review: Python Tutorial [video]`
- Tweet: `Review: Database Design Thread [tweet]`

## Error Handling Strategy
1. **OmniFocus configuration missing**: Fallback to Obsidian, set error message
2. **OmniFocus task creation fails**: Fallback to Obsidian, set error message
3. **Both fail**: Return `success=False` with error details

**Rationale**: Graceful degradation ensures data is never lost.

---

## Files to Modify (Complete List)

### Python Backend (2 files)
1. **`src/productivity_service/models/queue.py`**
   - Update 3 enum values + 1 docstring

2. **`src/productivity_service/routes/queue.py`**
   - Phase 1: ~15 renaming changes (constants, functions, docstrings, strings)
   - Phase 2: Add imports, 2 new functions, modify add_to_queue, update response model

### Chrome Extension (1 file)
3. **`chrome-extensions/bookmark-saver/background.js`**
   - Update 6 occurrences of read/review terminology

### Bookmarklet (3 files)
4. **`bookmarklet/bookmark-helper.html`**
   - Update 8 occurrences of read/review terminology

5. **`bookmarklet/README.md`**
   - Update 1 occurrence

6. **`bookmarklet/QUICK_START.md`**
   - Update 2 occurrences

### Documentation (2 files to rename + modify)
7. **`docs/READ_QUEUE.md` → `docs/REVIEW_QUEUE.md`**
   - Rename file + 30+ content updates

8. **`obsidian-templates/Reading Queue.md` → `obsidian-templates/Review Queue.md`**
   - Rename file + 20+ content updates (including 7 Dataview queries)

**Total: 8 files to modify, 2 files to rename**

---

## Migration Considerations

### Breaking Changes for Users
1. **Obsidian folder rename**: `ReadQueue/` → `ReviewQueue/`
   - Users must rename their folder manually OR
   - We keep backward compatibility by checking both folders (recommended)

2. **Queue status values changed**:
   - `unread` → `unreviewed`
   - `reading` → `reviewing`
   - Existing markdown files will have old values until re-saved

3. **Priority values changed**:
   - `must-read` → `must-review`
   - Affects Chrome extension context menu IDs

4. **Chrome extension menu items renamed**:
   - Users will see new labels immediately after update

### Backward Compatibility Strategy (Recommended)

**Option A: Support both folder names temporarily**
```python
# In _get_github_service or queue routes
QUEUE_FOLDERS = ["ReviewQueue", "ReadQueue"]  # Try new, fallback to old
```

**Option B: One-time migration script**
- Rename all files in `ReadQueue/` to `ReviewQueue/`
- Update all frontmatter status/priority values in existing files

**Recommendation**: Use Option A for 30 days, then remove old folder support. This gives users time to update their Obsidian templates.

---

## Environment Variables
**Already configured** (no changes needed):
- `PRODUCTIVITY_OMNIFOCUS_MAIL_DROP_ADDRESS`
- `PRODUCTIVITY_SES_SENDER_EMAIL`

---

## Testing Checklist

### Phase 1 Testing (Renaming)
- [ ] Python backend starts without errors
- [ ] API endpoints still work with old clients (backward compat)
- [ ] New queue items save to `ReviewQueue/` folder
- [ ] Frontmatter uses new values (`unreviewed`, `reviewing`, `must-review`)
- [ ] Chrome extension shows new menu labels ("Review Later", "Must Review")
- [ ] Bookmarklet shows new mode buttons and labels
- [ ] Documentation files renamed and updated correctly

### Phase 2 Testing (OmniFocus)
- [ ] Must-review with article URL → OmniFocus task created
- [ ] Must-review with Google Doc URL → OmniFocus task with `[gdoc]` type
- [ ] Must-review with video URL → OmniFocus task with `[video]` type
- [ ] Normal priority → Obsidian ReviewQueue (existing behavior)
- [ ] Snack priority → Obsidian ReviewQueue (existing behavior)
- [ ] OmniFocus failure → Fallback to Obsidian with error message
- [ ] Task format in OmniFocus inbox: `Review: {title} [{type}]`
- [ ] URL in task note for easy access
- [ ] Chrome extension "Must Review" creates OmniFocus task
- [ ] Bookmarklet "Must Review" creates OmniFocus task

### Integration Testing
- [ ] Test with various content types (article, gdoc, video, tweet, pdf, podcast)
- [ ] Test with missing metadata (fallback to URL as title)
- [ ] Test with very long titles (truncation)
- [ ] Test OmniFocus SES rate limiting (multiple rapid additions)
- [ ] Verify Obsidian Dataview queries work with new values
- [ ] Test backward compatibility with old folder/status names (if implemented)

---

## Post-Deployment Tasks

1. **Update user documentation** about folder rename
2. **Notify users** about Chrome extension menu changes
3. **Monitor logs** for OmniFocus failures in first week
4. **Update Obsidian templates** in user's vault (manual step for user)
5. **Consider migration script** for existing queue items (optional)
