# Things MCP Server Integration Test Plan

A test plan for Claude Cowork or Claude Code to execute via MCP tools. Claude follows this document step-by-step, making the appropriate MCP tool calls and tracking progress.

## Instructions for Claude

1. Execute each phase in order
2. Track UUIDs of all created items for cleanup
3. Mark checkboxes mentally as you complete each step
4. If any step fails, note the error and continue to the next step
5. Always complete Phase 6 (Cleanup) even if earlier phases had failures
6. Present the Phase 7 checklist to the user at the end

## Safety Rules

1. All test items MUST have prefix: `[MCP-TEST]`
2. All test items MUST use `when: "someday"` to avoid polluting Today/Upcoming
3. NEVER modify existing user data - only interact with items you create
4. At the end, mark all created items as `canceled: true` for cleanup
5. Track all created UUIDs for cleanup phase

---

## Phase 1: Read-Only Tools Verification

Test each read-only tool and verify it returns a valid response (either data or "No items found").

### 1.1 List View Tools
Call each tool and confirm it responds without error:

- [ ] `get_inbox` → Should return string response
- [ ] `get_today` → Should return string response
- [ ] `get_upcoming` → Should return string response
- [ ] `get_anytime` → Should return string response
- [ ] `get_someday` → Should return string response
- [ ] `get_logbook` with `period: "1d"`, `limit: 5` → Should return string response
- [ ] `get_trash` → Should return string response

### 1.2 Data Query Tools
- [ ] `get_todos` → Should return todos or "No todos found"
- [ ] `get_projects` → Should return projects or "No projects found"
- [ ] `get_areas` → Should return areas or "No areas found"
- [ ] `get_tags` → Should return tags or "No tags found"
  - **If tags exist:** Record one tag name to use in Phase 2.3 (for testing tag assignment)
  - **If no tags exist:** Skip tag-related tests (the API cannot create new tags)
- [ ] `get_headings` → Should return headings or "No headings found"

### 1.3 Search Tools
- [ ] `search_todos` with `query: "[MCP-TEST"` → Should return "No todos found" (verifies no stale test data)
- [ ] `search_advanced` with `status: "incomplete"` → Should return results or "No matching todos found"
- [ ] `get_recent` with `period: "1d"` → Should return results or "No items found"

**Phase 1 Complete when:** All tools respond without errors.

---

## Phase 2: Create Test Data

Create test items and record their UUIDs for later cleanup.

### 2.1 Create Test Project
Call `add_project` with:
```
title: "[MCP-TEST] Integration Test Project"
notes: "Automated test project - safe to delete"
when: "someday"
todos: ["[MCP-TEST] Project Task 1", "[MCP-TEST] Project Task 2"]
```

- [ ] Project created successfully

### 2.2 Create Basic Todo
Call `add_todo` with:
```
title: "[MCP-TEST] Basic Todo"
notes: "Basic test todo - safe to delete"
when: "someday"
```

- [ ] Basic todo created successfully

### 2.3 Create Full Featured Todo
Call `add_todo` with:
```
title: "[MCP-TEST] Full Featured Todo"
notes: "Testing all parameters"
when: "someday"
deadline: "2099-12-31"
checklist_items: ["Checklist item 1", "Checklist item 2", "Checklist item 3"]
```

**If an existing tag was found in Phase 1.2**, also include:
```
tags: ["<existing-tag-name>"]
```

- [ ] Full featured todo created successfully

### 2.4 Create Reminder Todo
Call `add_todo` with:
```
title: "[MCP-TEST] Reminder Todo"
notes: "Testing reminder functionality"
when: "2099-01-01@10:00"
```

- [ ] Reminder todo created successfully

**Phase 2 Complete when:** All 4 items created (1 project with 2 tasks + 3 standalone todos = 6 total items).

---

## Phase 3: Verify Created Items

### 3.1 Search for Test Items
Call `search_todos` with `query: "[MCP-TEST]"`

- [ ] Search returns results
- [ ] Results contain at least 5-6 items (project + todos)
- [ ] **Record all UUIDs** from the results for cleanup phase

### 3.2 Verify Tagged Items (Skip if no tags exist)
**Only if a tag was used in Phase 2.3:**

Call `get_tagged_items` with `tag: "<existing-tag-name>"`

- [ ] Returns the "Full Featured Todo" item among the results

### 3.3 Verify in Someday List
Call `get_someday`

- [ ] Results include test items with "[MCP-TEST]" prefix

**Phase 3 Complete when:** All created items are found and UUIDs recorded.

---

## Phase 4: Update Operations

### 4.1 Update a Todo
Using a todo UUID from Phase 3, call `update_todo` with:
```
id: "<UUID of Basic Todo>"
title: "[MCP-TEST] Basic Todo - UPDATED"
notes: "Updated via integration test"
```

- [ ] Update succeeds

### 4.2 Verify Todo Update
Call `search_todos` with `query: "UPDATED"`

- [ ] Returns the updated todo with new title

### 4.3 Update the Project
Using the project UUID from Phase 3, call `update_project` with:
```
id: "<UUID of Integration Test Project>"
title: "[MCP-TEST] Integration Test Project - UPDATED"
notes: "Project updated via integration test"
```

- [ ] Update succeeds

### 4.4 Verify Project Update
Call `search_todos` with `query: "Project - UPDATED"`

- [ ] Returns the updated project

**Phase 4 Complete when:** Both update operations verified.

---

## Phase 5: UI Navigation Tools

These tools open the Things app UI.

### 5.1 Show Today View
Call `show_item` with `id: "today"`

- [ ] Things app opens to Today view

### 5.2 Search in Things UI
Call `search_items` with `query: "[MCP-TEST]"`

- [ ] Things app shows search results with test items

**Phase 5 Complete when:** UI tools execute without error.

---

## Phase 6: Cleanup

Mark all test items as canceled. This removes them from active lists.

### 6.1 Cancel All Test Todos
For each todo UUID recorded in Phase 3, call `update_todo` with:
```
id: "<UUID>"
canceled: true
```

- [ ] All test todos marked as canceled

### 6.2 Cancel the Test Project
Call `update_project` with:
```
id: "<project UUID>"
canceled: true
```

- [ ] Test project marked as canceled

### 6.3 Verify Cleanup
Call `search_todos` with `query: "[MCP-TEST]"`

- [ ] Should return "No todos found matching" (all items now canceled)

**Phase 6 Complete when:** All test items canceled and no longer appear in search.

---

## Phase 7: Human Verification Checklist

Present this checklist to the user:

### Test Results Summary
Report:
- Total tests executed
- Tests passed
- Tests failed (if any)

### Manual Verification Steps
1. **Verify canceled items in Logbook:**
   - Open Things 3 app
   - Go to Logbook
   - Search for `[MCP-TEST]`
   - Confirm all test items appear with "Canceled" status

2. **Optional permanent cleanup:**
   - In Logbook, select all `[MCP-TEST]` items
   - Press Cmd+Delete to permanently delete
   - Empty Trash if desired

### Items Created During This Test Run
List all items with their UUIDs that were created and then canceled:
- Project: `[MCP-TEST] Integration Test Project - UPDATED`
- Todos:
  - `[MCP-TEST] Basic Todo - UPDATED`
  - `[MCP-TEST] Full Featured Todo`
  - `[MCP-TEST] Reminder Todo`
  - `[MCP-TEST] Project Task 1`
  - `[MCP-TEST] Project Task 2`

---

## Notes

- The Things URL scheme does not support permanent deletion, only marking items as canceled
- Canceled items appear in the Logbook and can be manually deleted if desired
- The Things URL scheme cannot create new tags - only existing tags can be assigned to items
- If a tag was used in testing, it will remain on the canceled items in the Logbook
