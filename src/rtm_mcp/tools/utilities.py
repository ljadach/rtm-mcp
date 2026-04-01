"""Utility tools for RTM MCP."""

from typing import Any

from fastmcp import Context

from ..response_builder import build_response


def register_utility_tools(mcp: Any, get_client: Any) -> None:
    """Register utility and diagnostic tools."""

    @mcp.tool()
    async def test_connection(ctx: Context) -> dict[str, Any]:
        """Test connectivity to the RTM API. Use this to diagnose connection issues
        before attempting other operations. Returns response time in milliseconds.

        Returns:
            {"status": "connected", "response_time_ms": N} on success, or
            {"status": "error", "error": "..."} on failure.
        """
        import time

        from ..client import RTMClient

        client: RTMClient = await get_client()

        start = time.monotonic()
        try:
            result = await client.test_echo()
            elapsed = time.monotonic() - start

            return build_response(
                data={
                    "status": "connected",
                    "response_time_ms": round(elapsed * 1000, 2),
                    "api_response": result,
                },
            )
        except Exception as e:
            elapsed = time.monotonic() - start
            return build_response(
                data={
                    "status": "error",
                    "error": str(e),
                    "response_time_ms": round(elapsed * 1000, 2),
                },
            )

    @mcp.tool()
    async def check_auth(ctx: Context) -> dict[str, Any]:
        """Verify that the stored auth token is valid and check permission level.
        Use this to confirm authentication before performing write operations.

        Returns:
            {"status": "authenticated", "user": {id, username, fullname},
            "permissions": "delete"} on success, or {"status": "not_authenticated"}.
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        try:
            result = await client.check_token()
            auth = result.get("auth", {})
            user = auth.get("user", {})

            return build_response(
                data={
                    "status": "authenticated",
                    "user": {
                        "id": user.get("id"),
                        "username": user.get("username"),
                        "fullname": user.get("fullname"),
                    },
                    "permissions": auth.get("perms"),
                },
            )
        except Exception as e:
            return build_response(
                data={
                    "status": "not_authenticated",
                    "error": str(e),
                },
            )

    @mcp.tool()
    async def get_tags(ctx: Context) -> dict[str, Any]:
        """Retrieve all tags used across your tasks, sorted alphabetically. Use this to
        discover existing tags before adding them to tasks, or to check tag names for
        use in list_tasks filters (e.g., filter="tag:work").

        Returns:
            {"tags": [{name}], "count": N}.
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        result = await client.call("rtm.tags.getList")

        tags_data = result.get("tags", {}).get("tag", [])
        if isinstance(tags_data, dict):
            tags_data = [tags_data]
        if isinstance(tags_data, str):
            tags_data = [{"name": tags_data}]

        tags = []
        for tag in tags_data:
            if isinstance(tag, str):
                tags.append({"name": tag})
            else:
                tags.append({
                    "name": tag.get("name", tag.get("$t", "")),
                })

        return build_response(
            data={
                "tags": sorted(tags, key=lambda x: x["name"]),
                "count": len(tags),
            },
        )

    @mcp.tool()
    async def get_locations(ctx: Context) -> dict[str, Any]:
        """Retrieve all saved locations. Locations can be assigned to tasks using
        the @location syntax in add_task, or filtered with list_tasks(filter="location:name").

        Returns:
            {"locations": [{id, name, latitude, longitude, zoom, address}], "count": N}.
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        result = await client.call("rtm.locations.getList")

        locations_data = result.get("locations", {}).get("location", [])
        if isinstance(locations_data, dict):
            locations_data = [locations_data]

        locations = []
        for loc in locations_data:
            locations.append({
                "id": loc.get("id"),
                "name": loc.get("name"),
                "latitude": float(loc.get("latitude", 0)),
                "longitude": float(loc.get("longitude", 0)),
                "zoom": int(loc.get("zoom", 0)) if loc.get("zoom") else None,
                "address": loc.get("address"),
            })

        return build_response(
            data={
                "locations": locations,
                "count": len(locations),
            },
        )

    @mcp.tool()
    async def get_settings(ctx: Context) -> dict[str, Any]:
        """Retrieve user account settings including timezone, date/time format
        preferences, default list, and language. Useful for understanding how dates
        and times will be interpreted.

        Returns:
            {"timezone": "...", "date_format": "European/American", "time_format":
            "12-hour/24-hour", "default_list_id": "...", "language": "..."}.
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        result = await client.call("rtm.settings.getList")

        settings = result.get("settings", {})

        # Format settings nicely
        date_format = "European (DD/MM/YY)" if settings.get("dateformat") == "0" else "American (MM/DD/YY)"
        time_format = "12-hour" if settings.get("timeformat") == "0" else "24-hour"

        return build_response(
            data={
                "timezone": settings.get("timezone"),
                "date_format": date_format,
                "time_format": time_format,
                "default_list_id": settings.get("defaultlist"),
                "language": settings.get("language"),
                "raw": settings,
            },
        )

    @mcp.tool()
    async def parse_time(
        ctx: Context,
        text: str,
        timezone: str | None = None,
    ) -> dict[str, Any]:
        """Parse a natural language time/date string into an ISO 8601 timestamp using
        RTM's parser. Useful for previewing how RTM will interpret date expressions
        before using them in set_task_due_date or set_task_start_date.

        Args:
            text: Time expression to parse (e.g., "tomorrow", "next friday", "in 2 hours",
                "dec 25", "3pm").
            timezone: IANA timezone (e.g., "America/New_York"). Defaults to UTC.

        Returns:
            {"input": "...", "parsed": "2026-04-02T00:00:00Z", "precision": "date"|"time"}.
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        params: dict[str, Any] = {"text": text}
        if timezone:
            params["timezone"] = timezone

        result = await client.call("rtm.time.parse", **params)

        time_data = result.get("time", {})

        return build_response(
            data={
                "input": text,
                "parsed": time_data.get("$t"),
                "precision": time_data.get("precision"),
            },
        )

    @mcp.tool()
    async def undo(
        ctx: Context,
        transaction_id: str,
    ) -> dict[str, Any]:
        """Undo a previous write operation using its transaction_id. Most write tools
        return a transaction_id in their metadata. Not all operations are undoable —
        check the "undoable" field in the original response. Must be called within
        the same session (timelines expire).

        Args:
            transaction_id: The transaction_id from the operation's response metadata.

        Returns:
            {"status": "success", "message": "Operation undone"} or
            {"status": "error", "error": "..."}.
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        try:
            await client.call(
                "rtm.transactions.undo",
                require_timeline=True,
                transaction_id=transaction_id,
            )

            client.mark_undone(transaction_id)

            return build_response(
                data={
                    "status": "success",
                    "message": "Operation undone",
                    "transaction_id": transaction_id,
                },
            )
        except Exception as e:
            return build_response(
                data={
                    "status": "error",
                    "error": str(e),
                    "transaction_id": transaction_id,
                },
            )

    @mcp.tool()
    async def batch_undo(
        ctx: Context,
        transaction_ids: list[str],
    ) -> dict[str, Any]:
        """Undo multiple write operations in reverse chronological order. All
        transaction_ids must belong to the current session's timeline. Processing
        stops on the first failure; already-undone transactions are skipped silently.

        Use get_timeline_info to see which transactions are available for undo.

        Args:
            transaction_ids: List of transaction_ids to undo (from response metadata
                or get_timeline_info).

        Returns:
            {"undone": [...], "skipped": [...], "failed": {...} | null,
            "timeline_id": "..."}.
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        # Validate all IDs exist in the transaction log
        unknown = [tid for tid in transaction_ids if client.get_transaction(tid) is None]
        if unknown:
            return build_response(
                data={
                    "error": f"Unknown transaction IDs (not in current session): {unknown}. Use get_timeline_info to see valid transaction IDs.",
                },
            )

        # Sort by log order descending (most recent first)
        all_transactions = client.get_all_transactions()
        log_order = {entry.transaction_id: i for i, entry in enumerate(all_transactions)}
        sorted_ids = sorted(transaction_ids, key=lambda tid: log_order[tid], reverse=True)

        undone: list[str] = []
        skipped: list[str] = []
        failed: dict[str, str] | None = None

        for tid in sorted_ids:
            entry = client.get_transaction(tid)
            if entry and entry.undone:
                skipped.append(tid)
                continue

            try:
                await client.call(
                    "rtm.transactions.undo",
                    require_timeline=True,
                    transaction_id=tid,
                )
                client.mark_undone(tid)
                undone.append(tid)
            except Exception as e:
                failed = {"transaction_id": tid, "error": str(e)}
                break

        return build_response(
            data={
                "undone": undone,
                "skipped": skipped,
                "failed": failed,
                "timeline_id": client.timeline_id,
            },
        )

    @mcp.tool()
    async def get_timeline_info(ctx: Context) -> dict[str, Any]:
        """Get information about the current session's timeline and transaction
        history. Use this to review what write operations have been performed and
        which can be undone. If no writes have been performed yet, timeline_id
        will be null.

        Returns:
            {"timeline_id": "..." | null, "created_at": "..." | null,
            "transaction_count": N, "transactions": [{transaction_id, method,
            undoable, undone, summary}]}.
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        transactions = client.get_all_transactions()

        return build_response(
            data={
                "timeline_id": client.timeline_id,
                "created_at": client.timeline_created_at,
                "transaction_count": len(transactions),
                "transactions": [
                    {
                        "transaction_id": entry.transaction_id,
                        "method": entry.method,
                        "undoable": entry.undoable,
                        "undone": entry.undone,
                        "summary": entry.summary,
                    }
                    for entry in transactions
                ],
            },
        )

    @mcp.tool()
    async def get_contacts(ctx: Context) -> dict[str, Any]:
        """Retrieve RTM contacts for task sharing. Contacts are users you can share
        tasks with via the RTM sharing feature. Use list_tasks with filter
        "isShared:true" to find shared tasks.

        Returns:
            {"contacts": [{id, fullname, username}], "count": N}.
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        result = await client.call("rtm.contacts.getList")

        contacts_data = result.get("contacts", {}).get("contact", [])
        if isinstance(contacts_data, dict):
            contacts_data = [contacts_data]

        contacts = []
        for contact in contacts_data:
            contacts.append({
                "id": contact.get("id"),
                "fullname": contact.get("fullname"),
                "username": contact.get("username"),
            })

        return build_response(
            data={
                "contacts": contacts,
                "count": len(contacts),
            },
        )

    @mcp.tool()
    async def get_groups(ctx: Context) -> dict[str, Any]:
        """Retrieve contact groups with member counts. Groups organize contacts for
        batch task sharing.

        Returns:
            {"groups": [{id, name, member_count}], "count": N}.
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        result = await client.call("rtm.groups.getList")

        groups_data = result.get("groups", {}).get("group", [])
        if isinstance(groups_data, dict):
            groups_data = [groups_data]

        groups = []
        for group in groups_data:
            contacts = group.get("contacts", {}).get("contact", [])
            if isinstance(contacts, dict):
                contacts = [contacts]

            groups.append({
                "id": group.get("id"),
                "name": group.get("name"),
                "member_count": len(contacts),
            })

        return build_response(
            data={
                "groups": groups,
                "count": len(groups),
            },
        )
