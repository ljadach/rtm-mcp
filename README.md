# RTM MCP Server

A production-quality [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server for [Remember The Milk](https://www.rememberthemilk.com/) task management.

Enables Claude to manage your tasks through natural language conversation.

## Features

- **Full RTM API Coverage**: 42 tools covering tasks, lists, tags, notes, and more
- **Subtask Hierarchy**: Full parent/child task support with `parent_task_id`, subtask counts, and nesting up to 3 levels
- **Smart Add Syntax**: Natural language task creation (`"Call mom ^tomorrow !1 #family"`)
- **Undo and Batch Undo**: All write operations return transaction IDs; undo one or many operations with `batch_undo`
- **Timeline Introspection**: Session transaction log with `get_timeline_info` for reviewing write history
- **Token Bucket Rate Limiting**: Burst to 3 RPS, sustain ~0.9 RPS with configurable safety margin
- **Automatic 503 Retry**: Escalating backoff (2s → 5s) with configurable retry budget
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
git clone https://github.com/ljadach/rtm-mcp.git
cd rtm-mcp
uv sync
```

## Setup

### 1. Get RTM API Credentials

RTM API keys are issued through a separate developer portal (not your account settings):

1. Go to [RTM API Key Registration](https://www.rememberthemilk.com/services/api/keys.rtm) — you may need to log in first
2. Click **"Apply for an API Key"**
3. Fill in the form — app name (e.g. "Claude MCP"), description, anything works
4. After submitting, you'll see your **API Key** and **Shared Secret** — save both

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
- *"Show me the subtasks of my Project Alpha task"*
- *"Create a subtask under the Website Redesign task"*
- *"Move the research task under the Q2 Planning parent"*
- *"Replace all tags on the report task with #review and #urgent"*
- *"Bump the priority of the deployment task up one level"*
- *"Undo that last operation"*
- *"Show me what changes I've made this session"*
- *"Undo the last 3 operations"*

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

## Subtask Hierarchy

Tasks support parent/child relationships up to 3 levels deep (RTM Pro required):

- **`parent_task_id`** is included in every task response, linking children to their parent
- **`subtask_count`** on each task shows how many subtasks appear in the current result set
- **Create subtasks** by passing `parent_task_id` to `add_task`
- **Reparent or promote** tasks with `set_parent_task` (pass empty `parent_task_id` to promote to top-level)
- **Filter by parent** using the `parent_task_id` parameter on `list_tasks`

## Available Tools

### Tasks
- `list_tasks` - List tasks with filters (supports `parent_task_id` to fetch subtasks of a specific parent)
- `add_task` - Create a new task (supports `parent_task_id` to create as subtask, `external_id` for external tracking)
- `complete_task` / `uncomplete_task` - Mark done or reopen
- `delete_task` - Remove a task
- `postpone_task` - Move due date by one day
- `move_task` - Move to different list
- `set_parent_task` - Move a task under a parent or promote to top-level
- `set_task_name` - Rename task
- `set_task_due_date` - Change due date
- `set_task_priority` - Set priority level
- `move_task_priority` - Shift priority up or down by one level
- `set_task_recurrence` - Set repeat pattern
- `set_task_start_date` - Set start date
- `set_task_estimate` - Set time estimate
- `set_task_url` - Attach URL
- `add_task_tags` / `remove_task_tags` - Manage tags incrementally
- `set_task_tags` - Replace all tags on a task in one call

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

### Undo and Timeline
- `undo` - Undo a single write operation
- `batch_undo` - Undo multiple operations in reverse chronological order
- `get_timeline_info` - View session timeline and full transaction history

### Utilities
- `test_connection` - Test API connectivity
- `check_auth` - Verify authentication
- `get_tags` - List all tags
- `get_locations` - List saved locations
- `get_settings` - View user settings
- `get_contacts` - List contacts for task sharing
- `get_groups` - List contact groups with member counts
- `parse_time` - Parse natural language time
- `get_rate_limit_status` - View rate limiter state and request statistics

## Configuration

### Environment Variables

```bash
# Required
RTM_API_KEY=your_api_key
RTM_SHARED_SECRET=your_shared_secret
RTM_AUTH_TOKEN=your_token

# Rate limiting (optional, sensible defaults)
RTM_BUCKET_CAPACITY=3          # Max burst size (tokens)
RTM_SAFETY_MARGIN=0.1          # 10% below RTM's 1 RPS limit
RTM_MAX_RETRIES=2              # Retries on HTTP 503
RTM_RETRY_DELAY_FIRST=2.0      # Seconds before first retry
RTM_RETRY_DELAY_SUBSEQUENT=5.0 # Seconds before 2nd+ retry
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
