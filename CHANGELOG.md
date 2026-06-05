# Changelog

## v0.8.1 - 2026-06-05

### Maintenance

- **FastMCP 3.x**: Migrated to FastMCP 3.x. The dependency pin was an open-ended `fastmcp>=2.0.0`, so fresh installs were already resolving FastMCP 3.x untested; the pin is now bounded to `fastmcp>=3.0.0,<4`. Runtime behaviour is unchanged — in 3.x the `@mcp.tool` decorator returns the original function, so the test suite was updated to call tool functions directly instead of via the removed `.fn` accessor. All 155 tests pass under FastMCP 3.4.0.

## v0.8.0 - 2026-06-04

### Bug fixes

- **URL Encoding**: Slashes in titles/notes/checklist items are now percent-encoded as `%2F`. Previously a title like "Example 2/13" was silently truncated at the slash by Things' URL parser. Affects every URL-scheme operation, not just project updates. ([#47][i47] / [#48][p48])
- **`get_today` Resilience**: `get_today` no longer crashes with `'<' not supported between instances of 'NoneType' and 'str'` when Things' Today view contains deadline-only overdue items mixed with dated ones. Falls back to a local, None-safe sort when the upstream `things.today()` sort hits this case. ([#43][i43] / [#49][p49])
- **Logbook Filter**: `get_logbook` now filters by completion date (`stop_date`) instead of creation date. Tasks created weeks ago but checked off recently now appear in the report; `7d` and `1w` periods return useful results. Period parsing accepts `d`/`w`/`m`/`y` and surfaces invalid period strings explicitly. ([#46][i46] / [#50][p50])

### Features

- **Checklist Updates on Existing Todos**: `update_todo` gains `checklist_items`, `prepend_checklist_items`, and `append_checklist_items` parameters. Existing tasks can now have their checklists edited without recreating the task and losing its UUID. ([#34][i34] / [#51][p51])
- **Tag Usage Report**: New `get_tag_usage` tool lists every tag with its open and total task counts, sorted by usage descending; `only_unused=True` narrows to cleanup candidates. `update_todo` gains an `add_tags` parameter (append) alongside the existing `tags` (replace). ([#14][i14] / [#52][p52])
- **Bulk Updates**: New `bulk_update_todos` tool applies the same change (`list`, `tags`/`add_tags`, `when`, `deadline`, `heading`, `completed`, `canceled`) to many to-dos in a single Things round-trip via the URL scheme's `json` endpoint. Replaces N sequential calls for weekly-review batch moves. Requires `THINGS_AUTH_TOKEN`. ([#22][i22] / [#53][p53])

### Internal

- **Formatters Refactor**: Centralised the duplicated `things.get`-with-fallback pattern in a new `_lookup_title` helper, and the four-times-duplicated Created/Modified date block in a new `_append_timestamps` helper. Behaviour unchanged — the 67 existing formatter tests all still pass.
- **Acknowledged Things-API Limits**: Recurrence creation ([#42][i42]) and standalone heading creation ([#10][i10]) cannot be implemented via Things' current URL scheme or AppleScript (`repetition rule` is read-only; headings can only be created inside a project's initial `create` operation). Documented upstream so future contributors don't waste time on the same dead ends.

[i47]: https://github.com/hald/things-mcp/issues/47
[i43]: https://github.com/hald/things-mcp/issues/43
[i46]: https://github.com/hald/things-mcp/issues/46
[i34]: https://github.com/hald/things-mcp/issues/34
[i14]: https://github.com/hald/things-mcp/issues/14
[i22]: https://github.com/hald/things-mcp/issues/22
[i42]: https://github.com/hald/things-mcp/issues/42
[i10]: https://github.com/hald/things-mcp/issues/10
[p48]: https://github.com/hald/things-mcp/pull/48
[p49]: https://github.com/hald/things-mcp/pull/49
[p50]: https://github.com/hald/things-mcp/pull/50
[p51]: https://github.com/hald/things-mcp/pull/51
[p52]: https://github.com/hald/things-mcp/pull/52
[p53]: https://github.com/hald/things-mcp/pull/53

## v0.7.3 - 2026-02-13

- **Someday Project Filtering**: Tasks belonging to Someday projects are now filtered out of Today, Upcoming, and Anytime views, matching Things UI behavior. The Someday view also includes tasks from Someday projects that Things.py reports as Anytime. Handles both direct project membership and tasks under headings in Someday projects.
- **Someday Inheritance Display**: Tasks in Someday projects now show `List: Someday (inherited from project)` in formatted output, making the inherited status visible.
- **Integration Test Plan**: Added view-isolation checks, positive-presence tests for Today/Anytime, and Upcoming verification for scheduled items

## v0.7.2 - 2026-01-31

- **Logging Fix**: Changed root logger from DEBUG to INFO to silence verbose third-party library logs
- **Documentation**: Added uvx troubleshooting section for Claude Desktop path issues

## v0.7.1 - 2026-01-28

- **Simplified MCPB**: MCPB package now uses uvx to fetch from PyPI (1KB vs 8KB)
- **Documentation**: Reorganized README with cleaner installation sections, promoted MCPB as one-click install

## v0.7.0 - 2026-01-28

- **Package Restructure**: Restructured as uvx-compatible package (`src/things_mcp/`) with proper entry points for direct execution via `uvx things-mcp`
- **CLI Entry Point**: Added `things-mcp` command as a package entry point
- **Documentation**: Updated README with uvx installation as recommended method

## v0.6.0 - 2026-01-14

- **Creation Date Filtering**: Added `last` parameter to `search_advanced` for filtering by creation date (e.g., '3d' for last 3 days, '1w' for last week)
- **DateTime Scheduling with Reminders**: Extended `when` parameter to support datetime format with reminders (`YYYY-MM-DD@HH:MM`)
- **HTTP Transport**: Added optional HTTP transport mode via environment variables (`THINGS_MCP_TRANSPORT`, `THINGS_MCP_HOST`, `THINGS_MCP_PORT`). Note: HTTP transport requires running the server directly and is not available when installed via the .mcpb package.
- **Background Execution Fix**: Changed URL execution from AppleScript to shell script with `open -g` to prevent Things from coming to foreground
- **Bug Fix**: Fixed `search_advanced` type parameter causing duplicate keyword argument error
- **MCP Integration Test Plan**: Added Claude-executable integration test plan (`docs/mcp_integration_test_plan.md`) for verifying MCP tools against a live Things database

## v0.5.0 - 2025-12-15

- **MCPB Package Format**: Migrated from DXT to MCPB package format for Claude Desktop extensions, using uv for runtime dependency resolution
- **Human-Readable Age Display**: Tasks now show "Age: X ago" and "Last modified: X ago" in natural language (e.g., "3 days ago", "2 weeks ago")

## v0.4.0 - 2025-08-18

- **DXT Package Support**: Added automated packaging system with manifest.json configuration
- **Improved README**: Recommended DXT as preferred installation option

## v0.3.1 - 2025-08-11

- **Heading Support**: Added get_headings() tool to list and filter headings by project
- **Checklist Items**: Include checklist items in todo responses (thanks @JoeDuncko)
- **Enhanced Formatting**: Projects now display associated headings, improved heading data formatting
- **Expanded Test Coverage**: Added comprehensive tests for heading functionality (10 new tests, 63 total)

## v0.2.0 - 2025-08-04

- **FastMCP Migration**: Migrated from basic MCP implementation to FastMCP for cleaner, more maintainable code (thanks @excelsier)
- **Background URL Execution**: Things URLs now execute without bringing the app to foreground for better user experience (thanks @cdzombak)
- **Comprehensive Unit Test Suite**: Added unit tests covering URL construction and data formatting functions
- **Moving Todos Between Projects**: Handle moving projects from one project to another project (thanks @underlow)
- **Enhanced README**: Improved installation instructions with clearer step-by-step process