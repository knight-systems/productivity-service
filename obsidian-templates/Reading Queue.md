# 📚 Reading Queue

## 🔥 Must Read
```dataview
TABLE WITHOUT ID
  link(file.path, title) as "Title",
  estimated_time + " min" as "Time",
  content_type as "Type",
  created as "Added"
FROM "ReadQueue"
WHERE queue_status = "unread" AND priority = "must-read"
SORT created DESC
```

## 🍿 Snacks (< 2 min)
```dataview
TABLE WITHOUT ID
  link(file.path, title) as "Title",
  estimated_time + " min" as "Time",
  content_type as "Type"
FROM "ReadQueue"
WHERE queue_status = "unread" AND priority = "snack"
SORT created DESC
```

## 📖 Up Next
```dataview
TABLE WITHOUT ID
  link(file.path, title) as "Title",
  estimated_time + " min" as "Time",
  content_type as "Type",
  created as "Added"
FROM "ReadQueue"
WHERE queue_status = "unread" AND priority = "normal"
SORT created DESC
LIMIT 20
```

## 🕐 Someday
```dataview
TABLE WITHOUT ID
  link(file.path, title) as "Title",
  content_type as "Type",
  created as "Added"
FROM "ReadQueue"
WHERE queue_status = "unread" AND priority = "someday"
SORT created DESC
```

## 📚 Currently Reading
```dataview
TABLE WITHOUT ID
  link(file.path, title) as "Title",
  estimated_time + " min" as "Time",
  last_touched as "Started"
FROM "ReadQueue"
WHERE queue_status = "reading"
SORT last_touched DESC
```

## ✅ Recently Consumed
```dataview
TABLE WITHOUT ID
  link(file.path, title) as "Title",
  content_type as "Type",
  consumed_at as "Finished"
FROM "ReadQueue"
WHERE queue_status = "consumed"
SORT consumed_at DESC
LIMIT 10
```

---

## Queue Stats
```dataview
TABLE WITHOUT ID
  length(rows) as "Count"
FROM "ReadQueue"
WHERE queue_status = "unread"
GROUP BY priority
```
