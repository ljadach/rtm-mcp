"""RTM MCP Server - Main entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from .client import RTMClient
from .config import RTMConfig
from .exceptions import RTMAuthError
from .tools import (
    register_list_tools,
    register_note_tools,
    register_task_tools,
    register_utility_tools,
)

# Global client instance
_client: RTMClient | None = None


@asynccontextmanager
async def lifespan(mcp: FastMCP) -> AsyncIterator[None]:
    """Manage server lifecycle - initialize and cleanup client."""
    global _client

    # Load config and create client
    config = RTMConfig.load()

    if not config.is_configured():
        print("RTM not configured. Run: rtm-setup")
        print("Or set environment variables: RTM_API_KEY, RTM_SHARED_SECRET, RTM_AUTH_TOKEN")
    else:
        _client = RTMClient(config)

    try:
        yield
    finally:
        if _client:
            await _client.close()


async def get_client() -> RTMClient:
    """Get the RTM client instance.

    Raises RTMAuthError if not configured.
    """
    if _client is None:
        raise RTMAuthError("RTM not configured. Run: rtm-setup")
    return _client


# Create FastMCP server
mcp = FastMCP(
    name="rtm-mcp",
    instructions="""
RTM MCP Server - Remember The Milk task management for Claude.

This server provides full access to Remember The Milk's task management features:

## Task Operations
- list_tasks: List tasks with filters (due date, tags, priority, list)
- add_task: Create tasks with Smart Add syntax (^date !priority #tags)
- complete_task / uncomplete_task: Mark tasks done or reopen
- delete_task: Remove tasks
- postpone_task: Push due date by one day
- set_task_*: Modify name, due date, priority, recurrence, estimate, URL

## Tag Operations
- add_task_tags / remove_task_tags: Manage task tags
- get_tags: List all tags in use

## Note Operations
- add_note / edit_note / delete_note: Manage task notes
- get_task_notes: View all notes on a task

## List Operations
- get_lists: List all task lists
- add_list / rename_list / delete_list: Manage lists
- archive_list / unarchive_list: Archive management

## Utilities
- test_connection: Verify API connectivity
- check_auth: Verify authentication
- get_settings: View user preferences
- undo: Undo previous operation using transaction_id

## Smart Add Syntax
When adding tasks, use Smart Add for quick entry:
- ^date: Due date (^tomorrow, ^next friday, ^dec 25)
- !priority: Priority level (!1 high, !2 medium, !3 low)
- #tag: Add tags (#work, #urgent)
- @location: Set location
- =estimate: Time estimate (=30min, =1h)
- *repeat: Recurrence (*daily, *every monday)

Example: "Call mom ^tomorrow !1 #family"
""",
    lifespan=lifespan,
)

# Register all tools
register_task_tools(mcp, get_client)
register_list_tools(mcp, get_client)
register_note_tools(mcp, get_client)
register_utility_tools(mcp, get_client)


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
