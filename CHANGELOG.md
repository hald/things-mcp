# Changelog

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