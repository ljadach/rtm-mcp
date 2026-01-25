"""Response builder for consistent MCP responses."""

from datetime import datetime
from typing import Any


def build_response(
    data: dict[str, Any] | list[Any],
    analysis: dict[str, Any] | None = None,
    transaction_id: str | None = None,
) -> dict[str, Any]:
    """Build a consistent response structure.

    Args:
        data: The main response data
        analysis: Optional analysis/insights
        transaction_id: Optional transaction ID for undo support

    Returns:
        Structured response dict
    """
    response = {
        "data": data,
        "metadata": {
            "fetched_at": datetime.now().isoformat(),
        },
    }

    if analysis:
        response["analysis"] = analysis

    if transaction_id:
        response["metadata"]["transaction_id"] = transaction_id

    return response


def _convert_due_date(due: str, timezone: str | None) -> str:
    """Convert RTM due date (UTC) to user's timezone.

    Args:
        due: Due date string from RTM (ISO 8601 format, typically with Z suffix)
        timezone: User's IANA timezone (e.g., 'Europe/Warsaw')

    Returns:
        ISO 8601 date string in user's timezone, or original if conversion fails
    """
    if not timezone:
        return due

    try:
        from zoneinfo import ZoneInfo

        # Parse the UTC date from RTM
        due_dt = datetime.fromisoformat(due.replace("Z", "+00:00"))

        # Convert to user's timezone
        user_tz = ZoneInfo(timezone)
        due_local = due_dt.astimezone(user_tz)

        # Return ISO format in user's timezone
        return due_local.isoformat()
    except Exception:
        # If conversion fails, return original
        return due


def format_task(
    task: dict[str, Any], include_ids: bool = True, timezone: str | None = None
) -> dict[str, Any]:
    """Format a task for response.

    Args:
        task: Raw task data from RTM
        include_ids: Whether to include task IDs
        timezone: User's IANA timezone for date conversion (e.g., 'Europe/Warsaw')

    Returns:
        Formatted task dict
    """
    # Convert due date to user's timezone
    due_display = None
    due_raw = task.get("due")
    if due_raw:
        due_display = _convert_due_date(due_raw, timezone)

    formatted = {
        "name": task.get("name", ""),
        "priority": _priority_label(task.get("priority", "N")),
        "due": due_display,
        "completed": task.get("completed") or None,
        "tags": task.get("tags", []),
        "url": task.get("url") or None,
        "notes_count": len(task.get("notes", [])),
    }

    if include_ids:
        formatted["id"] = task.get("id")
        formatted["taskseries_id"] = task.get("taskseries_id")
        formatted["list_id"] = task.get("list_id")

    return formatted


def format_list(lst: dict[str, Any]) -> dict[str, Any]:
    """Format a list for response."""
    return {
        "id": lst.get("id"),
        "name": lst.get("name"),
        "smart": lst.get("smart") == "1",
        "archived": lst.get("archived") == "1",
        "locked": lst.get("locked") == "1",
    }


def _priority_label(priority: str) -> str:
    """Convert priority code to label."""
    labels = {
        "1": "high",
        "2": "medium",
        "3": "low",
        "N": "none",
    }
    return labels.get(priority, "none")


def priority_to_code(priority: str | int | None) -> str:
    """Convert priority label/number to RTM code."""
    if priority is None:
        return "N"

    priority_str = str(priority).lower()

    mapping = {
        "high": "1",
        "1": "1",
        "medium": "2",
        "2": "2",
        "low": "3",
        "3": "3",
        "none": "N",
        "0": "N",
        "n": "N",
    }

    return mapping.get(priority_str, "N")


def parse_tasks_response(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse RTM tasks response into flat task list.

    RTM returns nested structure:
    tasks.list[].taskseries[].task[]

    We flatten this to a simple list with all IDs attached.
    """
    tasks = []
    task_lists = result.get("tasks", {}).get("list", [])

    if isinstance(task_lists, dict):
        task_lists = [task_lists]

    for tl in task_lists:
        list_id = tl.get("id")
        taskseries_list = tl.get("taskseries", [])

        if isinstance(taskseries_list, dict):
            taskseries_list = [taskseries_list]

        for ts in taskseries_list:
            task_data = ts.get("task", [])
            if isinstance(task_data, dict):
                task_data = [task_data]

            # Parse tags
            tags_data = ts.get("tags", [])
            if isinstance(tags_data, dict):
                tags = tags_data.get("tag", [])
                if isinstance(tags, str):
                    tags = [tags]
            else:
                tags = []

            # Parse notes
            notes_data = ts.get("notes", [])
            notes = []
            if isinstance(notes_data, dict):
                notes = notes_data.get("note", [])
                if isinstance(notes, dict):
                    notes = [notes]

            for t in task_data:
                tasks.append({
                    "id": t.get("id"),
                    "taskseries_id": ts.get("id"),
                    "list_id": list_id,
                    "name": ts.get("name"),
                    "due": t.get("due") or None,
                    "has_due_time": t.get("has_due_time") == "1",
                    "completed": t.get("completed") or None,
                    "deleted": t.get("deleted") or None,
                    "priority": t.get("priority", "N"),
                    "postponed": int(t.get("postponed", 0)),
                    "estimate": t.get("estimate") or None,
                    "tags": tags if tags else [],
                    "notes": notes,
                    "url": ts.get("url") or None,
                    "location_id": ts.get("location_id") or None,
                    "created": ts.get("created") or None,
                    "modified": ts.get("modified") or None,
                })

    return tasks


def parse_lists_response(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse RTM lists response."""
    lists = result.get("lists", {}).get("list", [])
    if isinstance(lists, dict):
        lists = [lists]

    return [
        {
            "id": lst.get("id"),
            "name": lst.get("name"),
            "deleted": lst.get("deleted") == "1",
            "locked": lst.get("locked") == "1",
            "archived": lst.get("archived") == "1",
            "position": int(lst.get("position", -1)),
            "smart": lst.get("smart") == "1",
            "sort_order": lst.get("sort_order"),
        }
        for lst in lists
    ]


def get_transaction_id(result: dict[str, Any]) -> str | None:
    """Extract transaction ID from response for undo support."""
    transaction = result.get("transaction", {})
    return transaction.get("id")
