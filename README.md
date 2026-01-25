# RTM MCP Server

A production-quality [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server for [Remember The Milk](https://www.rememberthemilk.com/) task management.

Enables Claude to manage your tasks through natural language conversation.

## Features

- **Full RTM API Coverage**: 30+ tools covering tasks, lists, tags, notes, and more
- **Smart Add Syntax**: Natural language task creation (`"Call mom ^tomorrow !1 #family"`)
- **Undo Support**: All write operations return transaction IDs for undo
- **Async Performance**: Built on httpx with connection pooling
- **Type Safety**: Full Pydantic models and type hints

## Installation

### Using uvx (Recommended)

```bash
uvx rtm-mcp
```

### Using pip

```bash
pip install rtm-mcp
```

### From Source

```bash
git clone https://github.com/lukasz/rtm-mcp.git
cd rtm-mcp
uv sync
```

## Setup

### 1. Get RTM API Credentials

1. Go to [RTM API Keys](https://www.rememberthemilk.com/services/api/keys.rtm)
2. Create a new API key
3. Note your **API Key** and **Shared Secret**

### 2. Run Setup

```bash
rtm-setup
```

This will:
- Prompt for your API credentials
- Open your browser for authorization
- Save the auth token to `~/.config/rtm-mcp/config.json`

### 3. Configure Claude Desktop

Add to `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rtm": {
      "command": "uvx",
      "args": ["rtm-mcp"]
    }
  }
}
```

## Usage

Once configured, you can ask Claude to manage your tasks:

- *"Show my tasks due today"*
- *"Add a task to buy groceries tomorrow, high priority"*
- *"Complete the grocery task"*
- *"What high priority tasks do I have?"*
- *"Move the meeting prep task to my Work list"*
- *"Add a note to the project task"*

## Smart Add Syntax

When adding tasks, use RTM's Smart Add syntax:

| Symbol | Meaning | Example |
|--------|---------|---------|
| `^` | Due date | `^tomorrow`, `^next friday` |
| `!` | Priority | `!1` (high), `!2` (medium), `!3` (low) |
| `#` | Tag | `#work`, `#urgent` |
| `@` | Location | `@home`, `@office` |
| `=` | Estimate | `=30min`, `=2h` |
| `*` | Repeat | `*daily`, `*every monday` |

Example: `"Review report ^friday !1 #work =1h *weekly"`

## Available Tools

### Tasks
- `list_tasks` - List tasks with filters
- `add_task` - Create a new task
- `complete_task` / `uncomplete_task` - Mark done or reopen
- `delete_task` - Remove a task
- `postpone_task` - Move due date by one day
- `move_task` - Move to different list
- `set_task_name` - Rename task
- `set_task_due_date` - Change due date
- `set_task_priority` - Set priority level
- `set_task_recurrence` - Set repeat pattern
- `set_task_start_date` - Set start date
- `set_task_estimate` - Set time estimate
- `set_task_url` - Attach URL
- `add_task_tags` / `remove_task_tags` - Manage tags

### Notes
- `add_note` - Add note to task
- `edit_note` - Edit existing note
- `delete_note` - Remove note
- `get_task_notes` - View all notes

### Lists
- `get_lists` - List all lists
- `add_list` - Create new list
- `rename_list` - Rename list
- `delete_list` - Delete list
- `archive_list` / `unarchive_list` - Archive management
- `set_default_list` - Set default list

### Utilities
- `test_connection` - Test API connectivity
- `check_auth` - Verify authentication
- `get_tags` - List all tags
- `get_locations` - List saved locations
- `get_settings` - View user settings
- `get_contacts` / `get_groups` - Contact management
- `parse_time` - Parse natural language time
- `undo` - Undo previous operation

## Configuration

### Environment Variables

```bash
RTM_API_KEY=your_api_key
RTM_SHARED_SECRET=your_shared_secret
RTM_AUTH_TOKEN=your_token
```

### Config File

`~/.config/rtm-mcp/config.json`:
```json
{
  "api_key": "your_api_key",
  "shared_secret": "your_shared_secret",
  "token": "your_token"
}
```

## Development

```bash
# Install dev dependencies
make dev

# Run linting
make lint

# Run tests
make test

# Run with coverage
make test/coverage

# Format code
make format
```

## Docker

```bash
docker build -t rtm-mcp .
docker run -it --rm \
  -e RTM_API_KEY \
  -e RTM_SHARED_SECRET \
  -e RTM_AUTH_TOKEN \
  rtm-mcp
```

Claude Desktop config for Docker:
```json
{
  "mcpServers": {
    "rtm": {
      "command": "docker",
      "args": ["run", "-i", "--rm",
        "-e", "RTM_API_KEY",
        "-e", "RTM_SHARED_SECRET",
        "-e", "RTM_AUTH_TOKEN",
        "rtm-mcp"]
    }
  }
}
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Remember The Milk](https://www.rememberthemilk.com/) for the excellent task management service
- [FastMCP](https://github.com/jlowin/fastmcp) for the MCP framework
- [Anthropic](https://anthropic.com/) for Claude and the MCP specification
