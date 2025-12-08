#!/usr/bin/osascript
-- Extract flagged tasks and inbox summary from OmniFocus
-- Returns JSON with tasks sorted by priority and inbox summary

on run
    set priorityAList to {}
    set priorityBList to {}
    set priorityCList to {}
    set noPriorityList to {}
    set inboxTitles to {}

    tell application "OmniFocus"
        tell default document
            -- Get flagged tasks that are:
            -- - not completed
            -- - flagged
            -- - not dropped
            -- - in an active project (or no project)
            -- - not deferred to the future
            set flaggedTasks to every flattened task whose (completed is false) and (flagged is true) and (effectively dropped is false)

            repeat with aTask in flaggedTasks
                -- Skip if in a non-active project (on hold, dropped, or completed)
                set includeTask to true
                try
                    set taskProject to containing project of aTask
                    if taskProject is not missing value then
                        set projectStatus to status of taskProject
                        if projectStatus is not active then
                            set includeTask to false
                        end if
                    end if
                end try

                -- Skip if deferred to future
                if includeTask then
                    try
                        set deferDate to defer date of aTask
                        if deferDate is not missing value then
                            if deferDate > (current date) then
                                set includeTask to false
                            end if
                        end if
                    end try
                end if

                if includeTask then
                    my processTask(aTask, priorityAList, priorityBList, priorityCList, noPriorityList)
                end if
            end repeat

            -- Get inbox items
            set inboxTasks to every inbox task whose completed is false
            repeat with aTask in inboxTasks
                set end of inboxTitles to name of aTask
            end repeat
        end tell
    end tell

    -- Combine in priority order: A, B, C, then no priority
    set taskList to priorityAList & priorityBList & priorityCList & noPriorityList

    -- Build final JSON
    set AppleScript's text item delimiters to ","
    set tasksJson to "[" & (taskList as string) & "]"

    -- Build inbox titles array
    set inboxJson to "["
    set inboxCount to count of inboxTitles
    repeat with i from 1 to inboxCount
        set inboxJson to inboxJson & my toJSON(item i of inboxTitles)
        if i < inboxCount then set inboxJson to inboxJson & ","
    end repeat
    set inboxJson to inboxJson & "]"

    set AppleScript's text item delimiters to ""

    -- Return combined JSON object
    return "{\"tasks\":" & tasksJson & ",\"inbox_count\":" & inboxCount & ",\"inbox_titles\":" & inboxJson & "}"
end run

on processTask(aTask, priorityAList, priorityBList, priorityCList, noPriorityList)
    tell application "OmniFocus"
        set taskTitle to name of aTask
        set taskProject to ""
        set taskTagList to {}
        set priorityTag to ""
        set sizeTag to ""

        -- Get project name
        try
            set taskProject to name of containing project of aTask
        on error
            set taskProject to ""
        end try

        -- Get tags and identify priority/size
        try
            set taskTagObjects to tags of aTask
            repeat with aTag in taskTagObjects
                set tagName to name of aTag
                set end of taskTagList to tagName

                -- Check for priority tags
                if tagName is "Priority A" then
                    set priorityTag to "A"
                else if tagName is "Priority B" then
                    set priorityTag to "B"
                else if tagName is "Priority C" then
                    set priorityTag to "C"
                end if

                -- Check for size tags
                if tagName is in {"XS", "S", "M", "L", "XL", "XXL"} then
                    set sizeTag to tagName
                end if
            end repeat
        end try

        -- Build tags string
        set AppleScript's text item delimiters to ","
        set tagString to taskTagList as string
        set AppleScript's text item delimiters to ""

        -- Build JSON object
        set jsonObj to "{" & ¬
            "\"title\":" & my toJSON(taskTitle) & "," & ¬
            "\"project\":" & my toJSON(taskProject) & "," & ¬
            "\"priority\":" & my toJSON(priorityTag) & "," & ¬
            "\"size\":" & my toJSON(sizeTag) & "," & ¬
            "\"tags\":" & my toJSON(tagString) & ¬
            "}"

        -- Add to appropriate priority list
        if priorityTag is "A" then
            set end of priorityAList to jsonObj
        else if priorityTag is "B" then
            set end of priorityBList to jsonObj
        else if priorityTag is "C" then
            set end of priorityCList to jsonObj
        else
            set end of noPriorityList to jsonObj
        end if
    end tell
end processTask

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
