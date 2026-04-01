# RTM MCP Server - Developer Documentation

## Architecture Overview

```
src/rtm_mcp/
├── server.py           # FastMCP server, lifespan, tool registration
├── client.py           # Async RTM API client with signing
├── config.py           # Pydantic settings (env + file)
├── types.py            # Pydantic models for type safety
├── exceptions.py       # RTMError hierarchy + ERROR_GUIDANCE recovery hints
├── response_builder.py # Consistent response formatting
├── tools/
│   ├── tasks.py        # Task CRUD + metadata + hierarchy (19 tools)
│   ├── lists.py        # List management (7 tools)
│   ├── notes.py        # Note operations (4 tools)
│   └── utilities.py    # Tags, locations, settings, undo, timeline (11 tools)
└── scripts/
    └── setup_auth.py   # Interactive auth setup CLI
```

## Key Patterns

### Tool Registration

Tools are registered via functions that receive the mcp instance and a client getter:

```python
def register_task_tools(mcp: Any, get_client: Any) -> None:
    @mcp.tool()
    async def list_tasks(ctx: Context, filter: str | None = None) -> dict:
        client: RTMClient = await get_client()
        result = await client.call("rtm.tasks.getList", filter=filter)
        return build_response(data=parse_tasks_response(result))
```

### Response Format

All tools return consistent structure:

```python
{
    "data": {...},                    # Main response data
    "analysis": {"insights": [...]},  # Optional insights
    "metadata": {
        "fetched_at": "ISO timestamp",
        "transaction_id": "...",       # For undo support (write ops only)
        "transaction_undoable": True,  # Whether undo is possible (write ops only)
        "timeline_id": "...",          # Session timeline ID (write ops only)
    }
}
```

### RTM Client

Async client with automatic:
- MD5 request signing
- Timeline creation for writes
- Rate limiting (1 RPS)
- Error code mapping to exceptions

```python
client = RTMClient(config)
result = await client.call("rtm.tasks.add", require_timeline=True, name="Task")
```

### Error Handling

Two layers of error handling:

**RTM API errors** — `raise_for_error()` in `exceptions.py` maps RTM error codes to exception classes (`RTMAuthError`, `RTMValidationError`, `RTMNotFoundError`, etc.) and appends recovery guidance from `ERROR_GUIDANCE`:

```python
# exceptions.py
ERROR_GUIDANCE: dict[int, str] = {
    98: "Re-run rtm-setup to get a fresh auth token.",
    340: "Call get_lists to see available list names.",
    341: "Call list_tasks to find the correct task name or IDs.",
    4040: "Subtask features require an RTM Pro account.",
    # ... 11 codes total
}

def raise_for_error(code: int, message: str) -> None:
    error_class = ERROR_CODE_MAP.get(code, RTMError)
    guidance = ERROR_GUIDANCE.get(code)
    full_message = f"{message} — {guidance}" if guidance else message
    raise error_class(full_message, code)
```

**Application-level errors** — `_resolve_task_ids` helpers (in both `tasks.py` and `notes.py`) and tool functions return actionable error messages via `build_response(data={"error": ...})` that guide agents to the correct next step:

```python
# Example: suggests the tool to call next
{"error": "Task not found: 'Buy milk'. Use list_tasks to search by filter or check spelling."}
{"error": "Provide either task_name (for search) or all three: task_id, taskseries_id, and list_id. Get these from list_tasks."}
{"error": "List 'Projects' not found. Use get_lists to see available list names."}
```

### Task Identification

RTM uses three IDs for task operations:
- `list_id`: Which list the task is in
- `taskseries_id`: The task series (for recurring tasks)
- `task_id`: The specific task instance

Tools accept either `task_name` (fuzzy search) or all three IDs.

### Subtask Hierarchy

RTM supports parent/child task relationships (Pro required, max 3 levels):

- **`parent_task_id`** is extracted from the `taskseries` element (not `task`) and appears as empty string for top-level tasks — the parser normalises this to `None`
- Subtasks are sibling taskseries entries under the same list, NOT nested inside their parent
- **`subtask_count`** is computed client-side from the current result set via `_apply_subtask_counts()` — it does not make a secondary API call
- `list_tasks` accepts a `parent_task_id` parameter: it injects `isSubtask:true` into the server-side filter, then applies client-side filtering by parent ID
- `add_task` accepts `parent_task_id` to create a task as a subtask
- `set_parent_task` reparents a task or promotes it to top-level (pass empty `parent_task_id`)
- If the parent is in a different list, the task is **implicitly moved** to that list
- Repeating tasks cannot be parents or children of other repeating tasks
- `isSubtask:true` is an **undocumented** RTM filter — client-side filtering by `parent_task_id` is the reliable fallback
- RTM error codes: 4040 = Pro required, 4050 = invalid parent, 4060 = max nesting exceeded, 4070 = repeating task conflict, 4080 = due date before start date, 4090 = self-parenting

### Write Response Format

RTM returns different JSON structures for reads vs writes:
- **Read** (`getList`): `{"tasks": {"list": [...]}}`
- **Write** (`add`, `complete`, `setTags`, etc.): `{"list": {...}}`

`parse_tasks_response` handles both via fallback:
```python
task_lists = result.get("tasks", {}).get("list", [])
if not task_lists and "list" in result:
    task_lists = result["list"]
```

## RTM API Quirks

### Response Normalization

RTM returns inconsistent structures. Always normalize:

```python
lists = result.get("lists", {}).get("list", [])
if isinstance(lists, dict):  # Single item comes as dict, not list
    lists = [lists]
```

### Timeline Requirement

All write operations require a timeline:

```python
await client.call("rtm.tasks.complete", require_timeline=True, ...)
```

### Transaction Log and Undo

All write tools record their transaction in an in-memory log on `RTMClient` via `record_and_build_response()`. This helper extracts the transaction ID and undoable flag, records the entry, and builds the response with `transaction_id`, `transaction_undoable`, and `timeline_id` metadata in one call:

```python
return record_and_build_response(client, result, data={...}, tool_name="add_task")
```

The transaction log (`client.get_all_transactions()`) enables:
- `get_timeline_info` — inspect the session's full write history
- `batch_undo` — undo multiple operations in reverse chronological order
- `undo` — marks the transaction as undone in the log after successful undo

Key classes:
- `TransactionEntry` (dataclass in `client.py`): `transaction_id`, `method`, `undoable`, `undone`, `summary`
- `record_and_build_response` (in `response_builder.py`): combines `get_transaction_info` + `client.record_transaction` + `build_response`

## Testing

### Unit Tests

```bash
make test
```

Tests use respx for HTTP mocking and a FakeMCP pattern for tool-level tests:

```python
# HTTP mocking with respx
@pytest.fixture
def mock_rtm(respx_mock):
    respx_mock.get(RTM_API_URL).mock(return_value=httpx.Response(200, json={...}))
```

```python
# FakeMCP pattern — captures @mcp.tool() decorated functions for unit testing
class FakeMCP:
    def __init__(self):
        self.tools = {}
    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator
```

Test files (225 tests total):
- `tests/test_client.py` — client signing, API calls, timeline caching, transaction log (16 tests)
- `tests/test_config.py` — config load/save, file fallback, corrupt JSON (10 tests)
- `tests/test_exceptions.py` — error code mapping including subtask codes 4040-4090 (16 tests)
- `tests/test_response_builder.py` — parser, formatter, get_transaction_info, record_and_build_response (40 tests)
- `tests/test_tools/test_task_tools.py` — all 19 task tools via FakeMCP (60 tests)
- `tests/test_tools/test_tasks.py` — `_apply_subtask_counts` and `_analyze_tasks` helpers (17 tests)
- `tests/test_tools/test_list_tools.py` — all 7 list tools via FakeMCP (16 tests)
- `tests/test_tools/test_note_tools.py` — all 4 note tools via FakeMCP (14 tests)
- `tests/test_tools/test_utility_tools.py` — all 11 utility tools via FakeMCP (33 tests)
- `tests/test_tools/test_lists.py` — list response filtering and sorting (3 tests)

### Integration Testing

Use MCP Inspector:

```bash
make inspect
# or
npx @modelcontextprotocol/inspector uv run rtm-mcp
```

### Manual Testing

```python
# Quick API test
python -c "
import asyncio
from rtm_mcp.config import RTMConfig
from rtm_mcp.client import RTMClient

async def test():
    config = RTMConfig.load()
    client = RTMClient(config)
    result = await client.test_echo()
    print(result)
    await client.close()

asyncio.run(test())
"
```

## Adding New Tools

1. Identify RTM API method from [docs](https://www.rememberthemilk.com/services/api/)
2. Add tool function in appropriate tools/*.py file
3. Write an enriched docstring following Anthropic's best practices: opening sentence (what + when), parameter semantics, return shape, examples, and edge cases
4. Use `require_timeline=True` for write operations
5. Return via `record_and_build_response()` for write tools (records transaction + builds response)
6. Use actionable error messages that suggest the next tool to call
7. Add tests (unit tests for helpers, FakeMCP tests for tool functions)

Example:

```python
@mcp.tool()
async def set_task_location(
    ctx: Context,
    location_id: str,
    task_name: str | None = None,
    task_id: str | None = None,
    taskseries_id: str | None = None,
    list_id: str | None = None,
) -> dict[str, Any]:
    """Assign a saved location to a task. Use get_locations to find location IDs.
    Use list_tasks with filter "location:name" to find tasks at a location.

    Identify the task by either task_name or all three IDs.

    Returns:
        {"message": "Location set"} with transaction_id for undo.
    """
    client: RTMClient = await get_client()
    ids = await _resolve_task_ids(client, task_name, task_id, taskseries_id, list_id)
    if "error" in ids:
        return build_response(data=ids)

    result = await client.call(
        "rtm.tasks.setLocation",
        require_timeline=True,
        location_id=location_id,
        **ids,
    )

    return record_and_build_response(
        client, result,
        data={"message": "Location set"},
        tool_name="set_task_location",
    )
```

## Deployment

### PyPI Release

```bash
uv build
uv publish
```

### Docker

```bash
docker build -t rtm-mcp .
docker push ghcr.io/ljadach/rtm-mcp
```

## Common Issues

### "RTM not configured"

Run `rtm-setup` or set environment variables.

### Rate Limiting

Client enforces 1 RPS. For bulk operations, results will be slower.

### Token Expiry

RTM tokens don't expire, but can be revoked. Re-run `rtm-setup` if needed.
