# Release Notes - Things MCP v1.0.0

## Major Features

### FastMCP Implementation
- Added modern FastMCP pattern with decorator-based tool registration
- Cleaner and more maintainable code structure
- Better error handling and validation

### New Tool Additions
- **Task Management**
  - `add-todo` - Create tasks with rich metadata and checklist items
  - `update-todo` - Update existing tasks with comprehensive options
  
- **Project Management**
  - `add-project` - Create projects with initial todos and metadata
  - `update-project` - Update existing projects with full control
  
- **Enhanced Search**
  - `search-advanced` - Multi-criteria search with filtering
  - `search-items` - Global search across all Things items
  - `search-todos` - Targeted todo search
  
- **Navigation & Time-based Features**
  - `show-item` - Open specific items directly in Things
  - `get-recent` - View recently created items
  - `get-tagged-items` - List items with specific tags

### Infrastructure Improvements
- Proper package structure for PyPI distribution
- GitHub Actions CI workflow for automated testing
- Comprehensive test suite for all new functionality
- Enhanced error handling and validation

### Documentation
- Updated README with comprehensive tool documentation
- Added CONTRIBUTING.md for contributor guidelines
- Added CHANGELOG.md for version history tracking

## Breaking Changes
- None. All original functionality is preserved for backward compatibility.

## Bugfixes
- Improved error handling for URL scheme interactions
- Better handling of special characters in task and project names
- Fixed issues with tag management

## Installation
```bash
pip install things-mcp
```

## Usage
```bash
# Run the FastMCP implementation
mcp dev things_fast_server.py

# Or install for persistent use
mcp install things_fast_server.py
```
