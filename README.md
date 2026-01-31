# Things MCP Server

This [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) server lets you use Claude Desktop to interact with your task management data in [Things 3](https://culturedcode.com/things) from Cultured Code. You can ask Claude to create tasks, analyze projects, help manage priorities, and more.

This server leverages the [Things.py](https://github.com/thingsapi/things.py) library and the [Things URL Scheme](https://culturedcode.com/things/help/url-scheme/). 

<a href="https://glama.ai/mcp/servers/t9cgixg2ah"><img width="380" height="200" src="https://glama.ai/mcp/servers/t9cgixg2ah/badge" alt="Things Server MCP server" /></a>

## Support the Project

If you find this project helpful, consider supporting its development:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/haldick)

## Features

- Access to all major Things lists (Inbox, Today, Upcoming, etc.)
- Project and area management
- Tag operations
- Advanced search capabilities
- Recent items
- Detailed item information including checklists
- Support for nested data (projects within areas, todos within projects)


## Installation

### Prerequisites
- macOS (Things 3 is Mac-only)
- Things 3 app with "Enable Things URLs" turned on (Settings → General)
- A MCP client, such as Claude Desktop or Claude Code
- [uv](https://docs.astral.sh/uv/) Python package manager: `brew install uv`

### Install via uvx (Any MCP Client)

Things MCP is published on PyPI and can be run directly with `uvx`:

```bash
uvx things-mcp
```

Configure your MCP client to use `uvx` with `things-mcp` as the argument.

### Claude Desktop

#### Option 1: One-Click Install (Recommended)

1. Download the latest file from the [releases page](https://github.com/hald/things-mcp/releases)
2. Double-click the `.mcpb` file
3. Done!

#### Option 2: Manual Config

1. Go to **Claude → Settings → Developer → Edit Config**
2. Add the Things server:

```json
{
  "mcpServers": {
    "things": {
      "command": "uvx",
      "args": ["things-mcp"]
    }
  }
}
```

3. Save and restart Claude Desktop

### Claude Code

```bash
claude mcp add-json things '{"command":"uvx","args":["things-mcp"]}'
```

To make it available globally (across all projects), add `-s user`:
```bash
claude mcp add-json -s user things '{"command":"uvx","args":["things-mcp"]}'
```

### Verify it's working

After installation:
- If using Claude Desktop, you should see "Things MCP" in the "Search and tools" list
- Try asking: "What's in my Things inbox?"

### Sample Usage with Claude Desktop
* "What's on my todo list today?"
* "Create a todo to pack for my beach vacation next week, include a packing checklist."
* "Evaluate my current todos using the Eisenhower matrix."
* "Help me conduct a GTD-style weekly review using Things."
* "Show me tasks that haven't been modified in over a month."

#### Tips
* Create a project in Claude with custom instructions that explains how you use Things and organize areas, projects, tags, etc. Tell Claude what information you want included when it creates a new task (eg asking it to include relevant details in the task description might be helpful).
* Try adding another MCP server that gives Claude access to your calendar. This will let you ask Claude to block time on your calendar for specific tasks, create todos from upcoming calendar events (eg prep for a meeting), etc.
* Use task ages to identify stale items: "Which tasks in my Anytime list are older than 2 weeks?"


## Available Tools

### List Views
- `get-inbox` - Get todos from Inbox
- `get-today` - Get todos due today
- `get-upcoming` - Get upcoming todos
- `get-anytime` - Get todos from Anytime list
- `get-someday` - Get todos from Someday list
- `get-logbook` - Get completed todos
- `get-trash` - Get trashed todos

### Basic Operations
- `get-todos` - Get todos, optionally filtered by project
- `get-projects` - Get all projects
- `get-areas` - Get all areas

### Tag Operations
- `get-tags` - Get all tags
- `get-tagged-items` - Get items with a specific tag

### Search Operations
- `search-todos` - Simple search by title/notes
- `search-advanced` - Advanced search with multiple filters

### Time-based Operations
- `get-recent` - Get recently created items

### Things URL Scheme Operations
- `add-todo` - Create a new todo
- `add-project` - Create a new project
- `update-todo` - Update an existing todo
- `update-project` - Update an existing project
- `show-item` - Show a specific item or list in Things
- `search-items` - Search for items in Things

## Tool Parameters

### get-todos
- `project_uuid` (optional) - Filter todos by project
- `include_items` (optional, default: true) - Include checklist items

### get-projects / get-areas / get-tags
- `include_items` (optional, default: false) - Include contained items

### search-advanced
- `status` - Filter by status (incomplete/completed/canceled)
- `start_date` - Filter by start date (YYYY-MM-DD)
- `deadline` - Filter by deadline (YYYY-MM-DD)
- `tag` - Filter by tag
- `area` - Filter by area UUID
- `type` - Filter by item type (to-do/project/heading)
- `last` - Filter by creation date (e.g., '3d' for last 3 days, '1w' for last week)

### get-recent
- `period` - Time period (e.g., '3d', '1w', '2m', '1y')

### Scheduling with Reminders (add-todo, add-project, update-todo, update-project)
- `when` - Accepts multiple formats:
  - Keywords: `today`, `tomorrow`, `evening`, `anytime`, `someday`
  - Date: `YYYY-MM-DD` (e.g., `2024-01-15`)
  - DateTime with reminder: `YYYY-MM-DD@HH:MM` (e.g., `2024-01-15@14:30`)

## Troubleshooting

If it's not working:

1. **Make sure Things 3 is installed and has been opened at least once**
   - The Things database needs to exist for the server to work

2. **Check that "Enable Things URLs" is turned on**
   - Open Things → Settings → General → Enable Things URLs

3. **Claude Desktop can't find `uvx`**
   - Install uv globally with Homebrew (`brew install uv`) 
   - **Alternative**: Use the full path to `uvx` in your config. Find it with `which uvx` (typically `/Users/USERNAME/.local/bin/uvx`)

## Development

### Running Tests

The project includes a comprehensive unit test suite for the URL scheme and formatter modules.

```bash
# Install test dependencies
uv sync --extra test

# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_url_scheme.py

# Run tests matching a pattern
uv run pytest -k "test_add_todo"
```

### MCP Integration Test

The project includes an integration test plan that can be executed by Claude (via Claude Cowork or Claude Code) to verify all MCP tools work correctly against a live Things database.

See [`docs/mcp_integration_test_plan.md`](docs/mcp_integration_test_plan.md) for the full test plan.

### Project Structure

```
things-mcp/
├── src/things_mcp/      # Main package
│   ├── __init__.py      # Package exports
│   ├── __main__.py      # Entry point for python -m
│   ├── server.py        # MCP server implementation
│   ├── url_scheme.py    # Things URL scheme implementation
│   └── formatters.py    # Data formatting utilities
├── tests/               # Unit tests
│   ├── conftest.py      # Test fixtures and configuration
│   ├── test_url_scheme.py
│   └── test_formatters.py
├── docs/                # Documentation
│   └── mcp_integration_test_plan.md  # Claude-executable integration test
├── manifest.json        # MCPB package manifest
├── build_mcpb.sh        # MCPB package build script
├── pyproject.toml       # Project dependencies, build config, and pytest config
├── .env.example         # Sample environment configuration
└── run.sh               # Convenience runner script
```

### HTTP Transport

By default, the server uses stdio transport for communication with MCP clients. For remote access scenarios, you can run the server with HTTP transport.

#### Configuration

Set these environment variables to enable HTTP transport:

| Variable | Default | Description |
|----------|---------|-------------|
| `THINGS_MCP_TRANSPORT` | `stdio` | Transport type: `stdio` or `http` |
| `THINGS_MCP_HOST` | `127.0.0.1` | HTTP server bind address |
| `THINGS_MCP_PORT` | `8000` | HTTP server port |

#### Example

```bash
# Using uvx
THINGS_MCP_TRANSPORT=http THINGS_MCP_HOST=0.0.0.0 THINGS_MCP_PORT=8000 uvx things-mcp

# Or from source
THINGS_MCP_TRANSPORT=http THINGS_MCP_HOST=0.0.0.0 THINGS_MCP_PORT=8000 uv run things-mcp
```

See `.env.example` for a sample configuration file.
