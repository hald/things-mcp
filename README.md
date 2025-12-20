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
- Recent items tracking
- Detailed item information including checklists
- Support for nested data (projects within areas, todos within projects)
- **Human-readable age display** - See how long tasks have been created and when they were last modified
  - Shows task age in natural language (e.g., "3 days ago", "2 weeks ago")
  - Displays both creation age and modification age
  - Helps identify stale tasks and recently updated items

### Task Age Display

When viewing tasks, the server automatically calculates and displays human-readable ages:

```
Title: Prepare presentation
Created: 2025-11-09T10:30:00
Age: 1 week ago
Modified: 2025-11-15T14:20:00
Last modified: 1 day ago
```

This makes it easy to:
- Identify tasks that have been sitting for a long time
- See recently created tasks at a glance
- Track when tasks were last updated
- Make better decisions about task prioritization

Age is displayed in natural language:
- **Same day**: "today"
- **Recent days**: "3 days ago"
- **Recent weeks**: "2 weeks ago"
- **Recent months**: "3 months ago"
- **Years**: "2 years ago"

## Installation

### Prerequisites
- macOS (Things 3 is Mac-only)
- A MCP client, such as Claude Desktop or Claude Code
- Things 3 app with "Enable Things URLs" turned on (Settings → General)
- [uv](https://docs.astral.sh/uv/) Python package manager: `brew install uv`

### MCPB Installation (Recommended for Claude Desktop)

MCP Bundles (.mcpb) provide the easiest way to install MCP servers.

1. Download the latest `things-mcp-0.5.0.mcpb` file from the [releases page](https://github.com/hald/things-mcp/releases)
2. Double-click the `.mcpb` file to install it in Claude Desktop
3. The extension will be automatically configured and ready to use

The MCPB package uses `uv` to automatically resolve and install the correct Python dependencies for your system architecture.

To setup Things MCP with Claude Code or other MCP clients, scroll down to the Manual Installation section.

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


### Available Tools

#### List Views
- `get-inbox` - Get todos from Inbox
- `get-today` - Get todos due today
- `get-upcoming` - Get upcoming todos
- `get-anytime` - Get todos from Anytime list
- `get-someday` - Get todos from Someday list
- `get-logbook` - Get completed todos
- `get-trash` - Get trashed todos

#### Basic Operations
- `get-todos` - Get todos, optionally filtered by project
- `get-projects` - Get all projects
- `get-areas` - Get all areas

#### Tag Operations
- `get-tags` - Get all tags
- `get-tagged-items` - Get items with a specific tag

#### Search Operations
- `search-todos` - Simple search by title/notes
- `search-advanced` - Advanced search with multiple filters

#### Time-based Operations
- `get-recent` - Get recently created items

#### Things URL Scheme Operations
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

### get-recent
- `period` - Time period (e.g., '3d', '1w', '2m', '1y')

## Manual Installation

For advanced users who prefer to install from source:

### Step 1: Clone the repository

Choose a location where you want to install Things MCP. For example, to install in your home directory:

```bash
cd ~
git clone https://github.com/hald/things-mcp
cd things-mcp
```

**Important**: Remember this location! You'll need the full path. You can get it by running:
```bash
pwd
```
This will show something like: `/Users/yourusername/things-mcp`

### Step 2: Install dependencies

```bash
uv sync
```

### Step 3: Configure Claude

#### For Claude Desktop:

1. Open Claude Desktop
2. Go to **Claude → Settings → Developer → Edit Config**
3. Add the Things server to the `mcpServers` section:

```json
{
  "mcpServers": {
    "things": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/yourusername/things-mcp",
        "run",
        "things_server.py"
      ]
    }
  }
}
```

**Replace `/Users/yourusername/things-mcp` with your actual path from Step 1!**

**Note**: If you installed uv outside of Homebrew, you may need to use the full path to uv in your MCP configuration. Common locations include:
- pip install: Usually in your Python environment's bin directory
- Standalone installer: `~/.local/bin/uv` or `~/.cargo/bin/uv`

To find your uv location, run:
```bash
which uv
```

4. Save the file and restart Claude Desktop

#### For Claude Code:

In your terminal, run:
```bash
claude mcp add-json things '{"command":"uv","args":["--directory","/path/to/things-mcp","run","things_server.py"]}'
```

**Replace `/path/to/things-mcp` with your actual path from Step 1!**

To make it available globally (across all projects), add `-s user`:
```bash
claude mcp add-json -s user things '{"command":"uv","args":["--directory","/path/to/things-mcp","run","things_server.py"]}'
```

### Step 4: Verify it's working

After restarting your MCP client:
- If using Claude Desktop, you should see "Things 3" in the "Search and tools" list
- Try asking: "What's in my Things inbox?"

### Troubleshooting

If it's not working:

1. **Make sure Things 3 is installed and has been opened at least once**
   - The Things database needs to exist for the server to work

2. **Check that "Enable Things URLs" is turned on**
   - Open Things → Settings → General → Enable Things URLs

3. **Verify the path in your configuration matches where you cloned the repository**
   - The path must be absolute (starting with `/`)
   - Run `pwd` in the things-mcp directory to get the correct path

4. **Check Claude's logs for errors:**
   ```bash
   tail -n 20 -f ~/Library/Logs/Claude/mcp*.log
   ```

5. **Common issues:**
   - "Could not attach to MCP" - Usually means the path is wrong
   - "spawn uv ENOENT" - Make sure uv was installed with Homebrew (`brew install uv`)
   - "No module named 'things'" - Run `uv sync` in the things-mcp directory
   - "Command not found: uv" - Install uv with Homebrew: `brew install uv`

6. **MCPB-specific issues:**
   - "No module named 'pydantic_core'" or similar binary module errors - Install uv (`brew install uv`) and restart Claude Desktop. The MCPB package requires uv to resolve dependencies at runtime.

### Updating

To update to the latest version:
```bash
cd ~/things-mcp  # or wherever you installed it
git pull
uv sync
```
Then restart Claude.

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

### Project Structure

```
things-mcp/
├── things_server.py     # Main MCP server implementation
├── url_scheme.py        # Things URL scheme implementation
├── formatters.py        # Data formatting utilities
├── tests/               # Unit tests
│   ├── conftest.py      # Test fixtures and configuration
│   ├── test_url_scheme.py
│   └── test_formatters.py
├── manifest.json        # MCPB package manifest
├── build_mcpb.sh        # MCPB package build script
├── pyproject.toml       # Project dependencies and pytest config
└── run.sh               # Convenience runner script
```
