# RTM MCP Server - Developer Documentation

## Architecture Overview

```
src/rtm_mcp/
├── server.py           # FastMCP server, lifespan, tool registration
├── client.py           # Async RTM API client with signing
├── config.py           # Pydantic settings (env + file)
├── types.py            # Pydantic models for type safety
├── exceptions.py       # RTMError hierarchy
├── response_builder.py # Consistent response formatting
├── tools/
│   ├── tasks.py        # Task CRUD + metadata (19 tools)
│   ├── lists.py        # List management (7 tools)
│   ├── notes.py        # Note operations (4 tools)
│   └── utilities.py    # Tags, locations, settings, undo
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
        "transaction_id": "..."       # For undo support
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

### Task Identification

RTM uses three IDs for task operations:
- `list_id`: Which list the task is in
- `taskseries_id`: The task series (for recurring tasks)
- `task_id`: The specific task instance

Tools accept either `task_name` (fuzzy search) or all three IDs.

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

### Transaction IDs

Write operations return transaction IDs for undo:

```python
transaction_id = result.get("transaction", {}).get("id")
```

## Testing

### Unit Tests

```bash
make test
```

Tests use respx for HTTP mocking:

```python
@pytest.fixture
def mock_rtm(respx_mock):
    respx_mock.get(RTM_API_URL).mock(return_value=httpx.Response(200, json={...}))
```

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
3. Use `require_timeline=True` for write operations
4. Return via `build_response()` with transaction_id if applicable
5. Add tests

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
    """Set task location."""
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

    return build_response(
        data={"message": "Location set"},
        transaction_id=get_transaction_id(result),
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
docker push ghcr.io/lukasz/rtm-mcp
```

## Common Issues

### "RTM not configured"

Run `rtm-setup` or set environment variables.

### Rate Limiting

Client enforces 1 RPS. For bulk operations, results will be slower.

### Token Expiry

RTM tokens don't expire, but can be revoked. Re-run `rtm-setup` if needed.
