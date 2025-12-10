# 📚 Review Queue

## 🔥 Must Review
```dataview
TABLE WITHOUT ID
  link(file.path, title) as "Title",
  estimated_time + " min" as "Time",
  content_type as "Type",
  created as "Added"
FROM "ReviewQueue"
WHERE queue_status = "unreviewed" AND priority = "must-review"
SORT created DESC
```

## 🍿 Snacks (< 2 min)
```dataview
TABLE WITHOUT ID
  link(file.path, title) as "Title",
  estimated_time + " min" as "Time",
  content_type as "Type"
FROM "ReviewQueue"
WHERE queue_status = "unreviewed" AND priority = "snack"
SORT created DESC
```

## 📖 Up Next
```dataview
TABLE WITHOUT ID
  link(file.path, title) as "Title",
  estimated_time + " min" as "Time",
  content_type as "Type",
  created as "Added"
FROM "ReviewQueue"
WHERE queue_status = "unreviewed" AND priority = "normal"
SORT created DESC
LIMIT 20
```

## 🕐 Someday
```dataview
TABLE WITHOUT ID
  link(file.path, title) as "Title",
  content_type as "Type",
  created as "Added"
FROM "ReviewQueue"
WHERE queue_status = "unreviewed" AND priority = "someday"
SORT created DESC
```

## 📚 Currently Reviewing
```dataview
TABLE WITHOUT ID
  link(file.path, title) as "Title",
  estimated_time + " min" as "Time",
  last_touched as "Started"
FROM "ReviewQueue"
WHERE queue_status = "reviewing"
SORT last_touched DESC
```

## ✅ Recently Consumed
```dataview
TABLE WITHOUT ID
  link(file.path, title) as "Title",
  content_type as "Type",
  consumed_at as "Finished"
FROM "ReviewQueue"
WHERE queue_status = "consumed"
SORT consumed_at DESC
LIMIT 10
```

---

## Queue Stats
```dataview
TABLE WITHOUT ID
  length(rows) as "Count"
FROM "ReviewQueue"
WHERE queue_status = "unreviewed"
GROUP BY priority
```
