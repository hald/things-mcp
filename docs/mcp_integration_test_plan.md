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
2. All test items MUST use `when: "someday"` to avoid polluting Today/Upcoming, except for brief positive-presence tests that immediately move items back to Someday
3. NEVER modify existing user data - only interact with items you create
4. At the end, mark all created items as `canceled: true` for cleanup
5. Track all created UUIDs for cleanup phase
6. The `add_area` tool can create Areas, but there is no MCP tool to cancel or delete them — any test Area created must be removed manually (flagged in Phases 6–7)

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
  - **Record the current list of area names** to confirm the test Area is newly created in Phase 3.7
- [ ] `get_tags` → Should return tags or "No tags found"
  - **If tags exist:** Record one tag name to use in Phase 2.3 (for testing tag assignment)
  - **If no tags exist:** Skip tag-related tests (the API cannot create new tags)
- [ ] `get_headings` → Should return headings or "No headings found"

### 1.3 Search Tools
- [ ] `search_todos` with `query: "[MCP-TEST"` → Should return "No todos found" (verifies no stale test data)
- [ ] `search_advanced` with `status: "incomplete"` → Should return results or "No matching todos found"
- [ ] `get_recent` with `period: "1d"` → Should return results or "No items found"

### 1.4 Structured Response & Pagination Verification

The read tools return **two channels** in every result: the human-readable **text** and a machine-readable **`structured_content`** object shaped `{items, count, total, offset, limit}`. `items` holds the full item dicts (the same data the text renders); the other keys are the pagination envelope. These checks confirm both channels are present and consistent, and that `limit`/`offset` shrink them together.

> **Client note:** these steps inspect the structured channel, which requires the MCP client to surface `structuredContent` to the model — Claude Desktop / Cowork do. If you are running in a client that only shows text, you can still verify everything except the raw envelope via the `Showing X-Y of Z items` text header.

Pick a list tool that Phase 1.1 showed returns **several items** (`get_someday`, `get_anytime`, or `get_todos` are usually the largest). Use the same tool for all steps below; call it **`<LIST>`**. If every list has fewer than 4 items, note that the lists are too small to exercise multi-page paging and verify only steps 1.4.1, 1.4.4, and 1.4.6.

**1.4.1 — Envelope present (unpaginated):**
Call `<LIST>` with no pagination arguments.

- [ ] Result includes a `structured_content` object with keys `items`, `count`, `total`, `offset`, `limit`
- [ ] `count` equals the number of entries in `items`
- [ ] With no pagination: `offset` == `0`, `limit` == `null`, and `total` == `count`
- [ ] **Record `total`** (call it `N`) for the steps below

**1.4.2 — `limit` shrinks both channels:**
Call `<LIST>` with `limit: 3` (and `offset: 0`).

- [ ] Structured: `count` ≤ 3, `limit` == `3`, `offset` == `0`, `total` == `N` (unchanged from 1.4.1)
- [ ] Structured: `items` length == `count`
- [ ] Text channel begins with header `Showing 1-3 of N items` (1-based)

**1.4.3 — Second page is disjoint:**
Call `<LIST>` with `limit: 3, offset: 3`.

- [ ] Structured: `offset` == `3`, `total` == `N`
- [ ] The `uuid`s in this page do **not** overlap with the `uuid`s from the 1.4.2 page (confirms paging advances)

**1.4.4 — Out-of-range offset reported distinctly:**
Call `<LIST>` with `offset: 100000`.

- [ ] Structured: `count` == `0`, `items` is empty, `total` == `N`, `offset` == `100000`
- [ ] Text channel reads `Showing 0 of N items (offset 100000 is past the end)` — distinct from an ordinary empty result

**1.4.5 — Channels agree:**
Using the 1.4.2 (`limit: 3`) result.

- [ ] The first item's `title`/`uuid` in structured `items` matches the first item rendered in the text channel (the two channels carry the same data)

**1.4.6 — Plain-string exception:**
Call `get_tag_usage`.

- [ ] Returns a plain-text report with **no** `structured_content` envelope — this is intentional (it is a compact report, not a list)

**Phase 1 Complete when:** All tools respond without errors, and the structured/pagination checks in 1.4 pass (envelope present and consistent, `limit`/`offset` page both channels together, out-of-range offset is reported distinctly, and `get_tag_usage` remains a plain-string report).

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
deadline: "2030-12-31"
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
when: "2030-01-01@10:00"
```

- [ ] Reminder todo created successfully

> **Why 2030 and not a far-future sentinel:** Things stores start dates in a packed integer whose **year field maxes out at 2047**. A date in 2048 or later (e.g. the old `2099` value used here) still sorts as "future" — so the item *does* land in Upcoming — but things.py cannot decode the year, and the structured `start_date` comes back `null`. Keep the year ≤ 2047 (a near-future date like 2030 is ideal) so structured-field checks see a real date. The same ceiling applies to `deadline` (see Phase 2.3).

### 2.5 Create Test Area
Call `add_area` with:
```
title: "[MCP-TEST] Integration Test Area"
```

- [ ] Area created successfully — **record the returned UUID** (the tool returns `Created new area: ... (id: <uuid>)`)
- [ ] ⚠️ This Area cannot be canceled or deleted via the MCP tools (there is no delete tool for Areas by design — deleting an Area in Things also deletes its child projects), so it will persist and must be removed manually in Phase 7

**Phase 2 Complete when:** All items created — 1 project with 2 tasks + 3 standalone todos + 1 area (7 total items).

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
- [ ] Results include `[MCP-TEST] Project Task 1` and `[MCP-TEST] Project Task 2`
- [ ] Project tasks show "(inherited from project)" annotation in formatted output
- [ ] The standalone todos (`Basic Todo`, `Full Featured Todo`) also appear

### 3.4 Verify View Isolation
These checks confirm that each list view contains only the items it should. Tasks belonging to Someday projects are filtered out of Today/Upcoming/Anytime, and items with a future start date appear in Upcoming.

**Check Anytime view:**
Call `get_anytime`

- [ ] Response does NOT contain `[MCP-TEST] Project Task 1`
- [ ] Response does NOT contain `[MCP-TEST] Project Task 2`
- [ ] Standalone Someday todos also do not appear (they are Someday, not Anytime)

**Check Today view:**
Call `get_today`

- [ ] Response does NOT contain `[MCP-TEST] Project Task 1`
- [ ] Response does NOT contain `[MCP-TEST] Project Task 2`

**Check Upcoming view:**
Call `get_upcoming`

- [ ] Response does NOT contain `[MCP-TEST] Project Task 1`
- [ ] Response does NOT contain `[MCP-TEST] Project Task 2`
- [ ] Response DOES contain `[MCP-TEST] Reminder Todo` — this item has `when: "2030-01-01@10:00"`, which sets a future start date, placing it in the Upcoming view rather than Someday
- [ ] **Structured-field check:** in the `get_upcoming` result's structured items, the Reminder Todo reports `start: "Someday"` with a populated `start_date` of `2030-01-01`. The `"Someday"` start value is correct — Things keeps future-scheduled items in the Someday start-bucket and surfaces them in Upcoming via their future `start_date` (this is exactly how `upcoming()` is defined). The `start_date` must be a real date, not `null` (a `null` here means the year exceeded the 2047 packed-date ceiling — see Phase 2.4)

### 3.5 Positive Presence in Today View
Temporarily create a Today item to confirm `get_today` surfaces test items, then move it to Someday to maintain cleanup safety.

**Create a Today todo:**
Call `add_todo` with:
```
title: "[MCP-TEST] Today Presence"
notes: "Temporary - will be moved to Someday immediately"
when: "today"
```

- [ ] Todo created successfully — **record UUID**

**Verify presence:**
Call `get_today`

- [ ] Response contains `[MCP-TEST] Today Presence`

**Move to Someday:**
Call `update_todo` with:
```
id: "<UUID of Today Presence>"
when: "someday"
```

- [ ] Update succeeds

**Verify removal:**
Call `get_today`

- [ ] Response does NOT contain `[MCP-TEST] Today Presence`

### 3.6 Positive Presence in Anytime View
Same pattern for Anytime. Create an Anytime item, verify, then move to Someday.

**Create an Anytime todo:**
Call `add_todo` with:
```
title: "[MCP-TEST] Anytime Presence"
notes: "Temporary - will be moved to Someday immediately"
when: "anytime"
```

- [ ] Todo created successfully — **record UUID**

**Verify presence:**
Call `get_anytime`

- [ ] Response contains `[MCP-TEST] Anytime Presence`

**Move to Someday:**
Call `update_todo` with:
```
id: "<UUID of Anytime Presence>"
when: "someday"
```

- [ ] Update succeeds

**Verify removal:**
Call `get_anytime`

- [ ] Response does NOT contain `[MCP-TEST] Anytime Presence`

### 3.7 Verify Area Creation
Call `get_areas`

- [ ] Response contains `[MCP-TEST] Integration Test Area`
- [ ] This area was NOT in the area list recorded in Phase 1.2 (confirms it was newly created, not pre-existing)

**Phase 3 Complete when:** All created items are found in Someday, project tasks show inherited annotation, project tasks are correctly excluded from Anytime/Today/Upcoming, the Reminder Todo appears in Upcoming, positive-presence tests pass for Today and Anytime views, and the new Area appears in `get_areas`.

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

### 4.5 Update the Area
Using the Area UUID from Phase 2.5, call `update_area` with:
```
id: "<UUID of Integration Test Area>"
title: "[MCP-TEST] Integration Test Area - UPDATED"
```

**If an existing tag was found in Phase 1.2**, also include:
```
tags: ["<existing-tag-name>"]
```

- [ ] Update succeeds

### 4.6 Verify Area Update
Call `get_areas`

- [ ] Response contains `[MCP-TEST] Integration Test Area - UPDATED`
- [ ] Response does NOT contain the old name `[MCP-TEST] Integration Test Area` (without "- UPDATED")

**Phase 4 Complete when:** Todo, project, and area update operations are all verified.

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
For each todo UUID recorded in Phases 2–3 (including the Today Presence and Anytime Presence items from 3.5/3.6), call `update_todo` with:
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

### 6.3 Test Area — Manual Cleanup Required
The MCP tools cannot cancel or delete Areas, so `[MCP-TEST] Integration Test Area - UPDATED` (renamed in Phase 4.5) will remain in Things after this phase.

- [ ] Record the Area UUID and name for manual deletion in Phase 7 (do NOT attempt an MCP cancel — there is no tool for it)

### 6.4 Verify Cleanup
Call `search_todos` with `query: "[MCP-TEST]"`

- [ ] Should return "No todos found matching" (all todos/project now canceled)

Call `get_areas`

- [ ] `[MCP-TEST] Integration Test Area - UPDATED` still appears (expected — it requires manual deletion)

**Phase 6 Complete when:** All test todos and the project are canceled and no longer appear in `search_todos`; the test Area is flagged for manual deletion.

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

3. **Required: delete the test Area manually** (the MCP tools cannot remove Areas):
   - In the Things sidebar, find `[MCP-TEST] Integration Test Area - UPDATED`
   - Right-click it → Delete (or select it and press Cmd+Delete)
   - Confirm it no longer appears in `get_areas`

### Items Created During This Test Run
List all items with their UUIDs that were created and then canceled:
- Project: `[MCP-TEST] Integration Test Project - UPDATED`
- Todos:
  - `[MCP-TEST] Basic Todo - UPDATED`
  - `[MCP-TEST] Full Featured Todo`
  - `[MCP-TEST] Reminder Todo`
  - `[MCP-TEST] Project Task 1`
  - `[MCP-TEST] Project Task 2`
  - `[MCP-TEST] Today Presence` (created in Phase 3.5, moved to Someday)
  - `[MCP-TEST] Anytime Presence` (created in Phase 3.6, moved to Someday)
- Area (⚠️ requires manual deletion — not cancelable via MCP):
  - `[MCP-TEST] Integration Test Area - UPDATED`

---

## Notes

- The Things URL scheme does not support permanent deletion, only marking items as canceled
- Canceled items appear in the Logbook and can be manually deleted if desired
- The Things URL scheme cannot create new tags - only existing tags can be assigned to items
- `add_area` and `update_area` manage Areas via AppleScript (the URL scheme has no area commands), but there is no MCP tool to delete an Area — deleting one in Things also deletes its child projects, so it is intentionally omitted. Test Areas must be removed manually in the Things app
- If a tag was used in testing, it will remain on the canceled items in the Logbook
- **Packed-date year ceiling (≤ 2047):** Things stores `start_date` and `deadline` as a packed integer with an 11-bit year field (max 2047). Dates from 2048 onward still sort as "future" (so items appear in Upcoming) but cannot be decoded by things.py, so the structured `start_date`/`deadline` come back `null`. This is an upstream things.py / Things on-disk-format limit, not a things-mcp bug. Tests use near-future dates (≤ 2047) so structured-field assertions see real values.
