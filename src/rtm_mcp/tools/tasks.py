"""Task management tools for RTM MCP."""

import contextlib
from typing import Any

from fastmcp import Context

from ..client import RTMClient
from ..response_builder import (
    build_response,
    format_task,
    get_transaction_id,
    parse_tasks_response,
    priority_to_code,
)


def _apply_subtask_counts(tasks: list[dict[str, Any]]) -> None:
    """Compute subtask_count on parent tasks from children in the result set."""
    task_ids = {t["id"] for t in tasks}
    counts: dict[str, int] = {}
    for t in tasks:
        pid = t.get("parent_task_id")
        if pid and pid in task_ids:
            counts[pid] = counts.get(pid, 0) + 1
    for t in tasks:
        t["subtask_count"] = counts.get(t["id"], 0)


def register_task_tools(mcp: Any, get_client: Any) -> None:
    """Register all task-related tools."""

    async def _get_user_timezone(client: RTMClient) -> str | None:
        """Fetch user's timezone from RTM settings."""
        try:
            settings_result = await client.call("rtm.settings.getList")
            return settings_result.get("settings", {}).get("timezone")
        except Exception:
            return None

    @mcp.tool()
    async def list_tasks(
        ctx: Context,
        filter: str | None = None,
        list_name: str | None = None,
        include_completed: bool = False,
        parent_task_id: str | None = None,
    ) -> dict[str, Any]:
        """List tasks with optional filtering.

        Args:
            filter: RTM filter string (e.g., "dueBefore:tomorrow", "tag:work", "priority:1")
            list_name: Filter to a specific list name
            include_completed: Include completed tasks (default: false)
            parent_task_id: Return only subtasks of this parent task ID

        Returns:
            List of tasks with metadata. subtask_count on each task reflects the
            number of children present in the current result set.

        Examples:
            - list_tasks() → all incomplete tasks
            - list_tasks(filter="dueBefore:tomorrow") → tasks due soon
            - list_tasks(filter="tag:work AND priority:1") → high priority work tasks
            - list_tasks(list_name="Personal") → tasks in Personal list
            - list_tasks(parent_task_id="1194808991") → subtasks of a specific parent
        """
        client: RTMClient = await get_client()

        # Build filter
        filter_parts = []
        if not include_completed:
            filter_parts.append("status:incomplete")
        if filter:
            filter_parts.append(filter)
        if parent_task_id:
            filter_parts.append("isSubtask:true")

        filter_str = " AND ".join(filter_parts) if filter_parts else None

        # Get list ID if name specified
        list_id = None
        if list_name:
            lists_result = await client.call("rtm.lists.getList")
            from ..response_builder import parse_lists_response

            lists = parse_lists_response(lists_result)
            for lst in lists:
                if lst["name"].lower() == list_name.lower():
                    if lst["smart"] and lst.get("filter"):
                        # Smart lists are saved filters; query by filter
                        # rather than list_id. Normalize non-breaking spaces
                        # (U+00A0) that RTM may include in filter strings.
                        smart_filter = lst["filter"].replace("\xa0", " ")
                        filter_parts.append(f"({smart_filter})")
                        filter_str = " AND ".join(filter_parts)
                    else:
                        list_id = lst["id"]
                    break

        params: dict[str, Any] = {}
        if filter_str:
            params["filter"] = filter_str
        if list_id:
            params["list_id"] = list_id

        result = await client.call("rtm.tasks.getList", **params)
        tasks = parse_tasks_response(result)

        # Filter completed if needed (belt and suspenders)
        if not include_completed:
            tasks = [t for t in tasks if not t.get("completed")]

        # Client-side filter by parent_task_id (RTM has no server-side operator)
        if parent_task_id:
            tasks = [t for t in tasks if t.get("parent_task_id") == parent_task_id]

        # Compute subtask_count for parent tasks in the result set
        _apply_subtask_counts(tasks)

        # Get user's timezone for accurate date display
        timezone = await _get_user_timezone(client)

        return build_response(
            data={
                "tasks": [format_task(t, timezone=timezone) for t in tasks],
                "count": len(tasks),
            },
            analysis=_analyze_tasks(tasks, timezone=timezone) if tasks else None,
        )

    @mcp.tool()
    async def add_task(
        ctx: Context,
        name: str,
        list_name: str | None = None,
        parse: bool = True,
        parent_task_id: str | None = None,
        external_id: str | None = None,
    ) -> dict[str, Any]:
        """Add a new task, optionally as a subtask of an existing task.

        Supports Smart Add syntax when parse=True:
            - ^date for due date (^tomorrow, ^next friday)
            - !priority (!1, !2, !3)
            - #tag for tags (#work, #urgent)
            - @location
            - =time estimate (=30min, =1h)
            - *repeat pattern (*daily, *weekly)

        Args:
            name: Task name (with optional Smart Add syntax)
            list_name: List to add to (uses default list if not specified)
            parse: Parse Smart Add syntax (default: True)
            parent_task_id: Task ID of the parent to create this as a subtask under (Pro only, max 3 levels)
            external_id: External reference ID to link the task to an external system (e.g., Jira ticket ID)

        Returns:
            Created task details with transaction ID for undo

        Examples:
            - add_task("Buy groceries")
            - add_task("Call mom ^tomorrow !1 #family")
            - add_task("Weekly review *weekly ^monday", list_name="Work")
            - add_task("Sub-item", parent_task_id="1194808991")
            - add_task("Fix login bug", external_id="JIRA-1234")
        """
        client: RTMClient = await get_client()

        params: dict[str, Any] = {
            "name": name,
            "parse": "1" if parse else "0",
        }

        if parent_task_id:
            params["parent_task_id"] = parent_task_id

        if external_id:
            params["external_id"] = external_id

        if list_name:
            lists_result = await client.call("rtm.lists.getList")
            from ..response_builder import parse_lists_response

            lists = parse_lists_response(lists_result)
            for lst in lists:
                if lst["name"].lower() == list_name.lower():
                    params["list_id"] = lst["id"]
                    break

        result = await client.call("rtm.tasks.add", require_timeline=True, **params)

        # Parse the created task
        tasks = parse_tasks_response(result)
        task = tasks[0] if tasks else {}
        transaction_id = get_transaction_id(result)
        timezone = await _get_user_timezone(client)

        return build_response(
            data={
                "task": format_task(task, timezone=timezone),
                "message": f"Created task: {task.get('name', name)}",
            },
            transaction_id=transaction_id,
        )

    @mcp.tool()
    async def complete_task(
        ctx: Context,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Mark a task as complete.

        Provide either task_name (for search) or all three IDs.

        Args:
            task_name: Task name to search for (fuzzy match)
            task_id: Specific task ID
            taskseries_id: Task series ID (required with task_id)
            list_id: List ID (required with task_id)

        Returns:
            Completed task details with transaction ID for undo
        """
        client: RTMClient = await get_client()

        # Find task if searching by name
        if task_name and not task_id:
            task = await _find_task(client, task_name)
            if not task:
                return build_response(
                    data={"error": f"Task not found: {task_name}"},
                )
            task_id = task["id"]
            taskseries_id = task["taskseries_id"]
            list_id = task["list_id"]

        if not all([task_id, taskseries_id, list_id]):
            return build_response(
                data={"error": "Must provide task_name or all three IDs"},
            )

        result = await client.call(
            "rtm.tasks.complete",
            require_timeline=True,
            list_id=list_id,
            taskseries_id=taskseries_id,
            task_id=task_id,
        )

        transaction_id = get_transaction_id(result)
        tasks = parse_tasks_response(result)
        task_data = tasks[0] if tasks else {}
        timezone = await _get_user_timezone(client)

        return build_response(
            data={
                "task": format_task(task_data, timezone=timezone),
                "message": f"Completed: {task_data.get('name', '')}",
            },
            transaction_id=transaction_id,
        )

    @mcp.tool()
    async def uncomplete_task(
        ctx: Context,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Reopen a completed task.

        Args:
            task_name: Task name to search for (searches completed tasks)
            task_id: Specific task ID
            taskseries_id: Task series ID
            list_id: List ID

        Returns:
            Reopened task details
        """
        client: RTMClient = await get_client()

        if task_name and not task_id:
            task = await _find_task(client, task_name, include_completed=True)
            if not task:
                return build_response(
                    data={"error": f"Completed task not found: {task_name}"},
                )
            if not task.get("completed"):
                return build_response(
                    data={"error": f"Task is not completed: {task_name}"},
                )
            task_id = task["id"]
            taskseries_id = task["taskseries_id"]
            list_id = task["list_id"]

        if not all([task_id, taskseries_id, list_id]):
            return build_response(
                data={"error": "Must provide task_name or all three IDs"},
            )

        result = await client.call(
            "rtm.tasks.uncomplete",
            require_timeline=True,
            list_id=list_id,
            taskseries_id=taskseries_id,
            task_id=task_id,
        )

        tasks = parse_tasks_response(result)
        task_data = tasks[0] if tasks else {}
        timezone = await _get_user_timezone(client)

        return build_response(
            data={
                "task": format_task(task_data, timezone=timezone),
                "message": f"Reopened: {task_data.get('name', '')}",
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def delete_task(
        ctx: Context,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Delete a task.

        Args:
            task_name: Task name to search for
            task_id: Specific task ID
            taskseries_id: Task series ID
            list_id: List ID

        Returns:
            Deletion confirmation with transaction ID for undo
        """
        client: RTMClient = await get_client()

        if task_name and not task_id:
            task = await _find_task(client, task_name)
            if not task:
                return build_response(
                    data={"error": f"Task not found: {task_name}"},
                )
            task_id = task["id"]
            taskseries_id = task["taskseries_id"]
            list_id = task["list_id"]
            deleted_name = task["name"]
        else:
            deleted_name = task_name or task_id

        if not all([task_id, taskseries_id, list_id]):
            return build_response(
                data={"error": "Must provide task_name or all three IDs"},
            )

        result = await client.call(
            "rtm.tasks.delete",
            require_timeline=True,
            list_id=list_id,
            taskseries_id=taskseries_id,
            task_id=task_id,
        )

        return build_response(
            data={"message": f"Deleted: {deleted_name}"},
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def set_task_name(
        ctx: Context,
        new_name: str,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Rename a task.

        Args:
            new_name: New name for the task
            task_name: Current task name to search for
            task_id: Specific task ID
            taskseries_id: Task series ID
            list_id: List ID

        Returns:
            Updated task details
        """
        client: RTMClient = await get_client()
        ids = await _resolve_task_ids(client, task_name, task_id, taskseries_id, list_id)
        if "error" in ids:
            return build_response(data=ids)

        result = await client.call(
            "rtm.tasks.setName",
            require_timeline=True,
            name=new_name,
            **ids,
        )

        tasks = parse_tasks_response(result)
        task_data = tasks[0] if tasks else {}
        timezone = await _get_user_timezone(client)

        return build_response(
            data={
                "task": format_task(task_data, timezone=timezone),
                "message": f"Renamed to: {new_name}",
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def set_task_due_date(
        ctx: Context,
        due: str,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Set or change task due date.

        Args:
            due: Due date (natural language: "tomorrow", "next friday", "2024-12-25")
                 Use empty string to clear due date.
            task_name: Task name to search for
            task_id: Specific task ID
            taskseries_id: Task series ID
            list_id: List ID

        Returns:
            Updated task details
        """
        client: RTMClient = await get_client()
        ids = await _resolve_task_ids(client, task_name, task_id, taskseries_id, list_id)
        if "error" in ids:
            return build_response(data=ids)

        result = await client.call(
            "rtm.tasks.setDueDate",
            require_timeline=True,
            due=due,
            parse="1",
            **ids,
        )

        tasks = parse_tasks_response(result)
        task_data = tasks[0] if tasks else {}
        timezone = await _get_user_timezone(client)

        message = f"Due date set to: {due}" if due else "Due date cleared"
        return build_response(
            data={
                "task": format_task(task_data, timezone=timezone),
                "message": message,
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def set_task_priority(
        ctx: Context,
        priority: str | int,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Set task priority.

        Args:
            priority: Priority level (1/high, 2/medium, 3/low, 0/N/none)
            task_name: Task name to search for
            task_id: Specific task ID
            taskseries_id: Task series ID
            list_id: List ID

        Returns:
            Updated task details
        """
        client: RTMClient = await get_client()
        ids = await _resolve_task_ids(client, task_name, task_id, taskseries_id, list_id)
        if "error" in ids:
            return build_response(data=ids)

        priority_code = priority_to_code(priority)

        result = await client.call(
            "rtm.tasks.setPriority",
            require_timeline=True,
            priority=priority_code,
            **ids,
        )

        tasks = parse_tasks_response(result)
        task_data = tasks[0] if tasks else {}
        timezone = await _get_user_timezone(client)

        return build_response(
            data={
                "task": format_task(task_data, timezone=timezone),
                "message": f"Priority set to: {priority}",
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def move_task_priority(
        ctx: Context,
        direction: str,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Move a task's priority up or down by one level.

        Up: none → low → medium → high. Down: high → medium → low → none.

        Args:
            direction: "up" or "down"
            task_name: Task name to search for
            task_id: Specific task ID
            taskseries_id: Task series ID
            list_id: List ID

        Returns:
            Updated task details with new priority
        """
        if direction not in ("up", "down"):
            return build_response(
                data={"error": f"Invalid direction: {direction}. Must be 'up' or 'down'."},
            )

        client: RTMClient = await get_client()
        ids = await _resolve_task_ids(client, task_name, task_id, taskseries_id, list_id)
        if "error" in ids:
            return build_response(data=ids)

        result = await client.call(
            "rtm.tasks.movePriority",
            require_timeline=True,
            direction=direction,
            **ids,
        )

        tasks = parse_tasks_response(result)
        task_data = tasks[0] if tasks else {}
        timezone = await _get_user_timezone(client)

        return build_response(
            data={
                "task": format_task(task_data, timezone=timezone),
                "message": f"Priority moved {direction}",
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def postpone_task(
        ctx: Context,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Postpone a task (moves due date by one day).

        Args:
            task_name: Task name to search for
            task_id: Specific task ID
            taskseries_id: Task series ID
            list_id: List ID

        Returns:
            Updated task details with new due date
        """
        client: RTMClient = await get_client()
        ids = await _resolve_task_ids(client, task_name, task_id, taskseries_id, list_id)
        if "error" in ids:
            return build_response(data=ids)

        result = await client.call(
            "rtm.tasks.postpone",
            require_timeline=True,
            **ids,
        )

        tasks = parse_tasks_response(result)
        task_data = tasks[0] if tasks else {}
        timezone = await _get_user_timezone(client)

        return build_response(
            data={
                "task": format_task(task_data, timezone=timezone),
                "message": "Task postponed",
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def move_task(
        ctx: Context,
        to_list_name: str,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Move a task to a different list.

        Args:
            to_list_name: Destination list name
            task_name: Task name to search for
            task_id: Specific task ID
            taskseries_id: Task series ID
            list_id: Current list ID (from_list_id)

        Returns:
            Updated task details
        """
        client: RTMClient = await get_client()

        # Find destination list
        lists_result = await client.call("rtm.lists.getList")
        from ..response_builder import parse_lists_response

        lists = parse_lists_response(lists_result)
        to_list_id = None
        for lst in lists:
            if lst["name"].lower() == to_list_name.lower():
                to_list_id = lst["id"]
                break

        if not to_list_id:
            return build_response(data={"error": f"List not found: {to_list_name}"})

        ids = await _resolve_task_ids(client, task_name, task_id, taskseries_id, list_id)
        if "error" in ids:
            return build_response(data=ids)

        result = await client.call(
            "rtm.tasks.moveTo",
            require_timeline=True,
            from_list_id=ids["list_id"],
            to_list_id=to_list_id,
            taskseries_id=ids["taskseries_id"],
            task_id=ids["task_id"],
        )

        tasks = parse_tasks_response(result)
        task_data = tasks[0] if tasks else {}
        timezone = await _get_user_timezone(client)

        return build_response(
            data={
                "task": format_task(task_data, timezone=timezone),
                "message": f"Moved to: {to_list_name}",
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def add_task_tags(
        ctx: Context,
        tags: str,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Add tags to a task.

        Args:
            tags: Comma-separated tags to add (e.g., "work,urgent")
            task_name: Task name to search for
            task_id: Specific task ID
            taskseries_id: Task series ID
            list_id: List ID

        Returns:
            Updated task details
        """
        client: RTMClient = await get_client()
        ids = await _resolve_task_ids(client, task_name, task_id, taskseries_id, list_id)
        if "error" in ids:
            return build_response(data=ids)

        result = await client.call(
            "rtm.tasks.addTags",
            require_timeline=True,
            tags=tags,
            **ids,
        )

        tasks = parse_tasks_response(result)
        task_data = tasks[0] if tasks else {}
        timezone = await _get_user_timezone(client)

        return build_response(
            data={
                "task": format_task(task_data, timezone=timezone),
                "message": f"Added tags: {tags}",
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def remove_task_tags(
        ctx: Context,
        tags: str,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Remove tags from a task.

        Args:
            tags: Comma-separated tags to remove
            task_name: Task name to search for
            task_id: Specific task ID
            taskseries_id: Task series ID
            list_id: List ID

        Returns:
            Updated task details
        """
        client: RTMClient = await get_client()
        ids = await _resolve_task_ids(client, task_name, task_id, taskseries_id, list_id)
        if "error" in ids:
            return build_response(data=ids)

        result = await client.call(
            "rtm.tasks.removeTags",
            require_timeline=True,
            tags=tags,
            **ids,
        )

        tasks = parse_tasks_response(result)
        task_data = tasks[0] if tasks else {}
        timezone = await _get_user_timezone(client)

        return build_response(
            data={
                "task": format_task(task_data, timezone=timezone),
                "message": f"Removed tags: {tags}",
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def set_task_tags(
        ctx: Context,
        tags: str,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Replace all tags on a task.

        This sets the complete tag list — any existing tags not in the new list
        will be removed. Use add_task_tags/remove_task_tags for incremental changes.

        Args:
            tags: Comma-separated tags to set (e.g., "work,action,urgent").
                  Empty string to clear all tags.
            task_name: Task name to search for
            task_id: Specific task ID
            taskseries_id: Task series ID
            list_id: List ID

        Returns:
            Updated task details with new tags
        """
        client: RTMClient = await get_client()
        ids = await _resolve_task_ids(client, task_name, task_id, taskseries_id, list_id)
        if "error" in ids:
            return build_response(data=ids)

        result = await client.call(
            "rtm.tasks.setTags",
            require_timeline=True,
            tags=tags,
            **ids,
        )

        tasks = parse_tasks_response(result)
        task_data = tasks[0] if tasks else {}
        timezone = await _get_user_timezone(client)

        message = f"Tags set to: {tags}" if tags else "All tags cleared"
        return build_response(
            data={
                "task": format_task(task_data, timezone=timezone),
                "message": message,
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def set_task_recurrence(
        ctx: Context,
        repeat: str,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Set task recurrence pattern.

        Args:
            repeat: Recurrence pattern (e.g., "every week", "every 2 days",
                   "every monday", "after 1 week"). Empty string to clear.
            task_name: Task name to search for
            task_id: Specific task ID
            taskseries_id: Task series ID
            list_id: List ID

        Returns:
            Updated task details
        """
        client: RTMClient = await get_client()
        ids = await _resolve_task_ids(client, task_name, task_id, taskseries_id, list_id)
        if "error" in ids:
            return build_response(data=ids)

        result = await client.call(
            "rtm.tasks.setRecurrence",
            require_timeline=True,
            repeat=repeat,
            **ids,
        )

        tasks = parse_tasks_response(result)
        task_data = tasks[0] if tasks else {}
        timezone = await _get_user_timezone(client)

        message = f"Recurrence set: {repeat}" if repeat else "Recurrence cleared"
        return build_response(
            data={
                "task": format_task(task_data, timezone=timezone),
                "message": message,
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def set_task_start_date(
        ctx: Context,
        start: str,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Set task start date.

        Args:
            start: Start date (natural language). Empty to clear.
            task_name: Task name to search for
            task_id: Specific task ID
            taskseries_id: Task series ID
            list_id: List ID

        Returns:
            Updated task details
        """
        client: RTMClient = await get_client()
        ids = await _resolve_task_ids(client, task_name, task_id, taskseries_id, list_id)
        if "error" in ids:
            return build_response(data=ids)

        result = await client.call(
            "rtm.tasks.setStartDate",
            require_timeline=True,
            start=start,
            parse="1",
            **ids,
        )

        tasks = parse_tasks_response(result)
        task_data = tasks[0] if tasks else {}
        timezone = await _get_user_timezone(client)

        message = f"Start date set: {start}" if start else "Start date cleared"
        return build_response(
            data={
                "task": format_task(task_data, timezone=timezone),
                "message": message,
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def set_task_estimate(
        ctx: Context,
        estimate: str,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Set task time estimate.

        Args:
            estimate: Time estimate (e.g., "30 minutes", "1 hour", "2 hours 30 minutes").
                     Empty to clear.
            task_name: Task name to search for
            task_id: Specific task ID
            taskseries_id: Task series ID
            list_id: List ID

        Returns:
            Updated task details
        """
        client: RTMClient = await get_client()
        ids = await _resolve_task_ids(client, task_name, task_id, taskseries_id, list_id)
        if "error" in ids:
            return build_response(data=ids)

        result = await client.call(
            "rtm.tasks.setEstimate",
            require_timeline=True,
            estimate=estimate,
            **ids,
        )

        tasks = parse_tasks_response(result)
        task_data = tasks[0] if tasks else {}
        timezone = await _get_user_timezone(client)

        message = f"Estimate set: {estimate}" if estimate else "Estimate cleared"
        return build_response(
            data={
                "task": format_task(task_data, timezone=timezone),
                "message": message,
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def set_task_url(
        ctx: Context,
        url: str,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Set task URL.

        Args:
            url: URL to attach to task. Empty to clear.
            task_name: Task name to search for
            task_id: Specific task ID
            taskseries_id: Task series ID
            list_id: List ID

        Returns:
            Updated task details
        """
        client: RTMClient = await get_client()
        ids = await _resolve_task_ids(client, task_name, task_id, taskseries_id, list_id)
        if "error" in ids:
            return build_response(data=ids)

        result = await client.call(
            "rtm.tasks.setURL",
            require_timeline=True,
            url=url,
            **ids,
        )

        tasks = parse_tasks_response(result)
        task_data = tasks[0] if tasks else {}
        timezone = await _get_user_timezone(client)

        message = f"URL set: {url}" if url else "URL cleared"
        return build_response(
            data={
                "task": format_task(task_data, timezone=timezone),
                "message": message,
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def set_parent_task(
        ctx: Context,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
        parent_task_id: str | None = None,
    ) -> dict[str, Any]:
        """Move a task under a parent (making it a subtask) or promote it to top-level.

        Pro accounts only. Max 3 levels of nesting.

        Args:
            task_name: Task name to search for
            task_id: Specific task ID
            taskseries_id: Task series ID
            list_id: List ID
            parent_task_id: New parent's task ID, or omit/None to make top-level

        Returns:
            Updated task details with transaction ID for undo
        """
        client: RTMClient = await get_client()
        ids = await _resolve_task_ids(client, task_name, task_id, taskseries_id, list_id)
        if "error" in ids:
            return build_response(data=ids)

        call_params: dict[str, Any] = {**ids}
        if parent_task_id:
            call_params["parent_task_id"] = parent_task_id

        result = await client.call(
            "rtm.tasks.setParentTask",
            require_timeline=True,
            **call_params,
        )

        tasks = parse_tasks_response(result)
        task_data = tasks[0] if tasks else {}
        timezone = await _get_user_timezone(client)

        if parent_task_id:
            message = f"Moved under parent task {parent_task_id}"
        else:
            message = "Promoted to top-level task"

        return build_response(
            data={
                "task": format_task(task_data, timezone=timezone),
                "message": message,
            },
            transaction_id=get_transaction_id(result),
        )


# Helper functions


async def _find_task(
    client: RTMClient,
    name: str,
    include_completed: bool = False,
) -> dict[str, Any] | None:
    """Find a task by name (fuzzy match)."""
    filter_str = "status:incomplete" if not include_completed else None

    if filter_str:
        result = await client.call("rtm.tasks.getList", filter=filter_str)
    else:
        result = await client.call("rtm.tasks.getList")
    tasks = parse_tasks_response(result)

    name_lower = name.lower()

    # Exact match first
    for task in tasks:
        if task["name"].lower() == name_lower:
            return task

    # Partial match
    for task in tasks:
        if name_lower in task["name"].lower():
            return task

    return None


async def _resolve_task_ids(
    client: RTMClient,
    task_name: str | None,
    task_id: str | None,
    taskseries_id: str | None,
    list_id: str | None,
) -> dict[str, Any]:
    """Resolve task identifiers, searching by name if needed."""
    if task_name and not task_id:
        task = await _find_task(client, task_name)
        if not task:
            return {"error": f"Task not found: {task_name}"}
        return {
            "task_id": task["id"],
            "taskseries_id": task["taskseries_id"],
            "list_id": task["list_id"],
        }

    if not all([task_id, taskseries_id, list_id]):
        return {"error": "Must provide task_name or all three IDs"}

    return {
        "task_id": task_id,
        "taskseries_id": taskseries_id,
        "list_id": list_id,
    }


def _parse_estimate_minutes(estimate: str | None) -> int | None:
    """Parse RTM estimate string to minutes. Returns None if unparseable.

    Handles both ISO 8601 durations (PT1H30M) and human-readable strings (1 hour 30 minutes).
    """
    if not estimate:
        return None
    import re

    total = 0
    matched = False

    # ISO 8601 duration: PT1H, PT30M, PT1H30M, PT2H15M
    iso = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?$", estimate)
    if iso:
        if iso.group(1):
            total += int(iso.group(1)) * 60
            matched = True
        if iso.group(2):
            total += int(iso.group(2))
            matched = True
        return total if matched else None

    # Human-readable: "1 hour", "30 minutes", "2 hours 30 minutes"
    hours = re.search(r"(\d+)\s*hour", estimate)
    minutes = re.search(r"(\d+)\s*min", estimate)
    if hours:
        total += int(hours.group(1)) * 60
    if minutes:
        total += int(minutes.group(1))
    return total if (hours or minutes) else None


def _analyze_tasks(tasks: list[dict[str, Any]], timezone: str | None = None) -> dict[str, Any]:
    """Generate analysis insights for tasks.

    Args:
        tasks: List of task dictionaries
        timezone: User's IANA timezone (e.g., 'Europe/Warsaw'). If not provided,
                  falls back to UTC which may cause incorrect date comparisons.
    """
    if not tasks:
        return {}

    priority_counts = {"high": 0, "medium": 0, "low": 0, "none": 0}
    overdue_count = 0
    due_today_count = 0
    total_estimate_minutes = 0
    without_estimate = 0
    tags_used: set[str] = set()

    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    # Get current date in user's timezone for accurate comparison
    # RTM due dates are relative to the user's timezone
    user_tz = None
    if timezone:
        with contextlib.suppress(Exception):
            user_tz = ZoneInfo(timezone)

    now = datetime.now(user_tz) if user_tz else datetime.now(UTC)
    today = now.date()

    for task in tasks:
        # Count priorities
        priority = task.get("priority", "N")
        if priority == "1":
            priority_counts["high"] += 1
        elif priority == "2":
            priority_counts["medium"] += 1
        elif priority == "3":
            priority_counts["low"] += 1
        else:
            priority_counts["none"] += 1

        # Check due dates
        due = task.get("due")
        if due:
            try:
                # Parse the due date from RTM
                # RTM returns dates in UTC with 'Z' suffix
                due_dt = datetime.fromisoformat(due.replace("Z", "+00:00"))

                # Convert to user's timezone for comparison
                if user_tz:
                    due_dt = due_dt.astimezone(user_tz)

                due_date = due_dt.date()
                if due_date < today:
                    overdue_count += 1
                elif due_date == today:
                    due_today_count += 1
            except ValueError:
                pass

        # Collect tags
        tags_used.update(task.get("tags", []))

        # Accumulate estimates
        est = task.get("estimate")
        est_minutes = _parse_estimate_minutes(est)
        if est_minutes is not None:
            total_estimate_minutes += est_minutes
        else:
            without_estimate += 1

    insights = []
    if overdue_count:
        insights.append(f"{overdue_count} overdue task(s)")
    if due_today_count:
        insights.append(f"{due_today_count} due today")
    if priority_counts["high"]:
        insights.append(f"{priority_counts['high']} high priority")
    if total_estimate_minutes:
        hours, mins = divmod(total_estimate_minutes, 60)
        if hours and mins:
            insights.append(f"{hours}h {mins}min total estimated")
        elif hours:
            insights.append(f"{hours}h total estimated")
        else:
            insights.append(f"{mins}min total estimated")
    if without_estimate:
        insights.append(f"{without_estimate} task(s) without estimate")

    return {
        "summary": {
            "total": len(tasks),
            "by_priority": priority_counts,
            "overdue": overdue_count,
            "due_today": due_today_count,
            "estimates": {
                "total_minutes": total_estimate_minutes,
                "total_display": f"{total_estimate_minutes // 60}h {total_estimate_minutes % 60}min",
                "without_estimate": without_estimate,
            },
        },
        "insights": insights,
        "tags_used": sorted(tags_used),
    }
