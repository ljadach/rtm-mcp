"""Utility tools for RTM MCP."""

from typing import Any

from fastmcp import Context

from ..response_builder import build_response


def register_utility_tools(mcp: Any, get_client: Any) -> None:
    """Register utility and diagnostic tools."""

    @mcp.tool()
    async def test_connection(ctx: Context) -> dict[str, Any]:
        """Test connection to RTM API.

        Returns:
            Connection status and response time
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
        """Check if authentication token is valid.

        Returns:
            Auth status and user info
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
        """Get all tags in use.

        Returns:
            List of tags with usage counts
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
        """Get all saved locations.

        Returns:
            List of locations
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
        """Get user settings.

        Returns:
            User preferences and settings
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
        """Parse a natural language time string.

        Args:
            text: Time to parse (e.g., "tomorrow", "next friday", "in 2 hours")
            timezone: Optional timezone (e.g., "America/New_York")

        Returns:
            Parsed time in various formats
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
        """Undo a previous operation.

        Use the transaction_id returned from write operations.

        Args:
            transaction_id: Transaction ID from previous operation

        Returns:
            Undo confirmation
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        try:
            await client.call(
                "rtm.transactions.undo",
                require_timeline=True,
                transaction_id=transaction_id,
            )

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
    async def get_contacts(ctx: Context) -> dict[str, Any]:
        """Get contacts for task sharing.

        Returns:
            List of contacts
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
        """Get contact groups.

        Returns:
            List of groups with member counts
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
