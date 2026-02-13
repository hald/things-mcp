# Changelog

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