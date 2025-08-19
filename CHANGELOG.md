# Changelog

## v0.4.0 - 2025-08-18

- **DXT Package Support**: Added automated DXT packaging system with build_dxt.sh script and manifest.json configuration
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