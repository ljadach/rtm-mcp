"""Note management tools for RTM MCP."""

from typing import Any

from fastmcp import Context

from ..response_builder import (
    build_response,
    get_transaction_id,
    parse_tasks_response,
)


def register_note_tools(mcp: Any, get_client: Any) -> None:
    """Register all note-related tools."""

    @mcp.tool()
    async def add_note(
        ctx: Context,
        note_text: str,
        note_title: str = "",
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Add a text note to a task. Tasks can have multiple notes. Use get_task_notes
        to see existing notes on a task.

        Args:
            note_text: The note body content.
            note_title: Optional title for the note (appears as a heading).
            task_name: Task name to search for (fuzzy match), or provide all three IDs.
            task_id, taskseries_id, list_id: Task IDs from list_tasks output.

        Returns:
            {"note": {id, title, body, created}, "message": "Note added"} with
            transaction_id for undo.
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()
        ids = await _resolve_task_ids(client, task_name, task_id, taskseries_id, list_id)
        if "error" in ids:
            return build_response(data=ids)

        params: dict[str, Any] = {
            "note_text": note_text,
            **ids,
        }
        if note_title:
            params["note_title"] = note_title

        result = await client.call(
            "rtm.tasks.notes.add",
            require_timeline=True,
            **params,
        )

        note = result.get("note", {})

        return build_response(
            data={
                "note": {
                    "id": note.get("id"),
                    "title": note.get("title", ""),
                    "body": note.get("$t", note.get("body", "")),
                    "created": note.get("created"),
                },
                "message": "Note added",
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def edit_note(
        ctx: Context,
        note_id: str,
        note_text: str,
        note_title: str = "",
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Edit an existing note's content and/or title. Get the note_id from
        get_task_notes. Requires all three task IDs or a task_name.

        Args:
            note_id: ID of the note to edit (from get_task_notes).
            note_text: New body content (replaces existing).
            note_title: New title (optional, empty string to clear).
            task_name: Task name to search for, or provide all three IDs.
            task_id, taskseries_id, list_id: Task IDs from list_tasks output.

        Returns:
            {"note": {id, title, body, modified}, "message": "Note updated"} with
            transaction_id.
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()
        ids = await _resolve_task_ids(client, task_name, task_id, taskseries_id, list_id)
        if "error" in ids:
            return build_response(data=ids)

        result = await client.call(
            "rtm.tasks.notes.edit",
            require_timeline=True,
            note_id=note_id,
            note_title=note_title,
            note_text=note_text,
            **ids,
        )

        note = result.get("note", {})

        return build_response(
            data={
                "note": {
                    "id": note.get("id"),
                    "title": note.get("title", ""),
                    "body": note.get("$t", note.get("body", "")),
                    "modified": note.get("modified"),
                },
                "message": "Note updated",
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def delete_note(
        ctx: Context,
        note_id: str,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Delete a note from a task. Get the note_id from get_task_notes. The
        deletion can be reversed with undo using the returned transaction_id.

        Args:
            note_id: ID of the note to delete (from get_task_notes).
            task_name: Task name to search for, or provide all three IDs.
            task_id, taskseries_id, list_id: Task IDs from list_tasks output.

        Returns:
            {"message": "Note deleted"} with transaction_id for undo.
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()
        ids = await _resolve_task_ids(client, task_name, task_id, taskseries_id, list_id)
        if "error" in ids:
            return build_response(data=ids)

        result = await client.call(
            "rtm.tasks.notes.delete",
            require_timeline=True,
            note_id=note_id,
            **ids,
        )

        return build_response(
            data={"message": "Note deleted"},
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def get_task_notes(
        ctx: Context,
        task_name: str | None = None,
        task_id: str | None = None,
        taskseries_id: str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve all notes attached to a task. Use this to find note IDs needed
        by edit_note and delete_note. Use list_tasks with filter "hasNotes:true" to
        find tasks that have notes.

        Identify the task by either task_name or all three IDs.

        Returns:
            {"task_name": "...", "notes": [{id, title, body, created, modified}],
            "count": N}.
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        # Find the task with its notes
        if task_name and not task_id:
            result = await client.call("rtm.tasks.getList")
            tasks = parse_tasks_response(result)

            name_lower = task_name.lower()
            task = None
            for t in tasks:
                if t["name"].lower() == name_lower or name_lower in t["name"].lower():
                    task = t
                    break

            if not task:
                return build_response(data={"error": f"Task '{task_name}' not found. Use list_tasks to find the correct name or IDs."})
        else:
            if not all([task_id, taskseries_id, list_id]):
                return build_response(
                    data={"error": "Provide either task_name (for search) or all three: task_id, taskseries_id, and list_id. Get these from list_tasks."},
                )
            # Fetch the specific task
            result = await client.call("rtm.tasks.getList", list_id=list_id)
            tasks = parse_tasks_response(result)
            task = None
            for t in tasks:
                if t["id"] == task_id and t["taskseries_id"] == taskseries_id:
                    task = t
                    break

            if not task:
                return build_response(data={"error": "Task not found with provided IDs. Use list_tasks to verify task_id, taskseries_id, and list_id."})

        notes = task.get("notes", [])
        if isinstance(notes, dict):
            notes = [notes]

        formatted_notes = []
        for note in notes:
            formatted_notes.append({
                "id": note.get("id"),
                "title": note.get("title", ""),
                "body": note.get("$t", note.get("body", "")),
                "created": note.get("created"),
                "modified": note.get("modified"),
            })

        return build_response(
            data={
                "task_name": task.get("name"),
                "notes": formatted_notes,
                "count": len(formatted_notes),
            },
        )


# Helper functions


async def _find_task(client: Any, name: str) -> dict[str, Any] | None:
    """Find a task by name (fuzzy match)."""
    result = await client.call("rtm.tasks.getList", filter="status:incomplete")
    tasks = parse_tasks_response(result)

    name_lower = name.lower()

    for task in tasks:
        if task["name"].lower() == name_lower:
            return task

    for task in tasks:
        if name_lower in task["name"].lower():
            return task

    return None


async def _resolve_task_ids(
    client: Any,
    task_name: str | None,
    task_id: str | None,
    taskseries_id: str | None,
    list_id: str | None,
) -> dict[str, Any]:
    """Resolve task identifiers."""
    if task_name and not task_id:
        task = await _find_task(client, task_name)
        if not task:
            return {"error": f"Task not found: '{task_name}'. Use list_tasks to search by filter or check spelling."}
        return {
            "task_id": task["id"],
            "taskseries_id": task["taskseries_id"],
            "list_id": task["list_id"],
        }

    if not all([task_id, taskseries_id, list_id]):
        return {"error": "Provide either task_name (for search) or all three: task_id, taskseries_id, and list_id. Get these from list_tasks."}

    return {
        "task_id": task_id,
        "taskseries_id": taskseries_id,
        "list_id": list_id,
    }
