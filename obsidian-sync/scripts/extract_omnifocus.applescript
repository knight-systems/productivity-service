#!/usr/bin/osascript
-- Extract today's tasks from OmniFocus
-- Returns JSON array of flagged tasks and tasks due today

on run
    set taskList to {}

    tell application "OmniFocus"
        tell default document
            -- Get flagged tasks that are not completed
            set flaggedTasks to every flattened task whose (completed is false) and (flagged is true)

            repeat with aTask in flaggedTasks
                set taskTitle to name of aTask
                set taskProject to ""
                set taskTagList to ""

                -- Get project name
                try
                    set taskProject to name of containing project of aTask
                on error
                    set taskProject to ""
                end try

                -- Get tags as comma-separated string
                try
                    set taskTagObjects to tags of aTask
                    set tagNames to {}
                    repeat with aTag in taskTagObjects
                        set end of tagNames to name of aTag
                    end repeat
                    set AppleScript's text item delimiters to ","
                    set taskTagList to tagNames as string
                    set AppleScript's text item delimiters to ""
                end try

                -- Build JSON object
                set jsonObj to "{" & ¬
                    "\"title\":" & my toJSON(taskTitle) & "," & ¬
                    "\"project\":" & my toJSON(taskProject) & "," & ¬
                    "\"flagged\":true," & ¬
                    "\"tags\":" & my toJSON(taskTagList) & ¬
                    "}"

                set end of taskList to jsonObj
            end repeat

            -- Also get tasks from "Today" perspective or due soon
            -- Using the inbox and available tasks
            set todayTasks to every flattened task whose (completed is false) and (flagged is false) and (next defer date is missing value or next defer date <= (current date))

            -- Limit to first 20 to avoid timeout
            set taskCount to 0
            repeat with aTask in todayTasks
                if taskCount >= 20 then exit repeat

                set taskTitle to name of aTask
                set taskProject to ""
                set taskTagList to ""

                -- Get project name
                try
                    set taskProject to name of containing project of aTask
                on error
                    set taskProject to ""
                end try

                -- Get tags
                try
                    set taskTagObjects to tags of aTask
                    set tagNames to {}
                    repeat with aTag in taskTagObjects
                        set end of tagNames to name of aTag
                    end repeat
                    set AppleScript's text item delimiters to ","
                    set taskTagList to tagNames as string
                    set AppleScript's text item delimiters to ""
                end try

                -- Only include if has a project (skip inbox items without context)
                if taskProject is not "" then
                    set jsonObj to "{" & ¬
                        "\"title\":" & my toJSON(taskTitle) & "," & ¬
                        "\"project\":" & my toJSON(taskProject) & "," & ¬
                        "\"flagged\":false," & ¬
                        "\"tags\":" & my toJSON(taskTagList) & ¬
                        "}"

                    set end of taskList to jsonObj
                    set taskCount to taskCount + 1
                end if
            end repeat
        end tell
    end tell

    -- Join into JSON array
    set AppleScript's text item delimiters to ","
    set jsonArray to "[" & (taskList as string) & "]"
    set AppleScript's text item delimiters to ""

    return jsonArray
end run

on toJSON(str)
    if str is "" or str is missing value then
        return "\"\""
    end if

    -- Escape special characters
    set str to str as string
    set str to my replaceText(str, "\\", "\\\\")
    set str to my replaceText(str, "\"", "\\\"")
    set str to my replaceText(str, return, "\\n")
    set str to my replaceText(str, linefeed, "\\n")
    set str to my replaceText(str, tab, "\\t")

    return "\"" & str & "\""
end toJSON

on replaceText(theText, searchStr, replaceStr)
    set AppleScript's text item delimiters to searchStr
    set theItems to text items of theText
    set AppleScript's text item delimiters to replaceStr
    set theText to theItems as string
    set AppleScript's text item delimiters to ""
    return theText
end replaceText
