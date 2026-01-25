"""List management tools for RTM MCP."""

from typing import Any

from fastmcp import Context

from ..response_builder import (
    build_response,
    format_list,
    get_transaction_id,
    parse_lists_response,
)


def register_list_tools(mcp: Any, get_client: Any) -> None:
    """Register all list-related tools."""

    @mcp.tool()
    async def get_lists(
        ctx: Context,
        include_archived: bool = False,
        include_smart: bool = True,
    ) -> dict[str, Any]:
        """Get all RTM lists.

        Args:
            include_archived: Include archived lists (default: false)
            include_smart: Include smart lists (default: true)

        Returns:
            List of all lists with metadata
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        result = await client.call("rtm.lists.getList")
        lists = parse_lists_response(result)

        # Filter based on preferences
        if not include_archived:
            lists = [lst for lst in lists if not lst["archived"]]
        if not include_smart:
            lists = [lst for lst in lists if not lst["smart"]]

        # Sort by position
        lists.sort(key=lambda x: (x["position"] if x["position"] >= 0 else 9999, x["name"]))

        return build_response(
            data={
                "lists": [format_list(lst) for lst in lists],
                "count": len(lists),
            },
        )

    @mcp.tool()
    async def add_list(
        ctx: Context,
        name: str,
        filter: str | None = None,
    ) -> dict[str, Any]:
        """Create a new list.

        Args:
            name: Name for the new list
            filter: Optional RTM filter to make this a smart list

        Returns:
            Created list details with transaction ID
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        params: dict[str, Any] = {"name": name}
        if filter:
            params["filter"] = filter

        result = await client.call("rtm.lists.add", require_timeline=True, **params)

        # Parse the created list
        lst = result.get("list", {})
        transaction_id = get_transaction_id(result)

        return build_response(
            data={
                "list": format_list(lst),
                "message": f"Created list: {name}",
            },
            transaction_id=transaction_id,
        )

    @mcp.tool()
    async def rename_list(
        ctx: Context,
        list_name: str,
        new_name: str,
    ) -> dict[str, Any]:
        """Rename a list.

        Args:
            list_name: Current name of the list
            new_name: New name for the list

        Returns:
            Updated list details
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        # Find list by name
        lists_result = await client.call("rtm.lists.getList")
        lists = parse_lists_response(lists_result)

        list_id = None
        for lst in lists:
            if lst["name"].lower() == list_name.lower():
                list_id = lst["id"]
                break

        if not list_id:
            return build_response(data={"error": f"List not found: {list_name}"})

        result = await client.call(
            "rtm.lists.setName",
            require_timeline=True,
            list_id=list_id,
            name=new_name,
        )

        lst = result.get("list", {})

        return build_response(
            data={
                "list": format_list(lst),
                "message": f"Renamed '{list_name}' to '{new_name}'",
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def delete_list(
        ctx: Context,
        list_name: str,
    ) -> dict[str, Any]:
        """Delete a list.

        Note: Lists with tasks cannot be deleted. Move or delete tasks first.

        Args:
            list_name: Name of the list to delete

        Returns:
            Deletion confirmation with transaction ID
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        # Find list by name
        lists_result = await client.call("rtm.lists.getList")
        lists = parse_lists_response(lists_result)

        list_id = None
        for lst in lists:
            if lst["name"].lower() == list_name.lower():
                if lst["locked"]:
                    return build_response(data={"error": f"Cannot delete locked list: {list_name}"})
                list_id = lst["id"]
                break

        if not list_id:
            return build_response(data={"error": f"List not found: {list_name}"})

        result = await client.call(
            "rtm.lists.delete",
            require_timeline=True,
            list_id=list_id,
        )

        return build_response(
            data={"message": f"Deleted list: {list_name}"},
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def archive_list(
        ctx: Context,
        list_name: str,
    ) -> dict[str, Any]:
        """Archive a list.

        Args:
            list_name: Name of the list to archive

        Returns:
            Updated list details
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        lists_result = await client.call("rtm.lists.getList")
        lists = parse_lists_response(lists_result)

        list_id = None
        for lst in lists:
            if lst["name"].lower() == list_name.lower():
                list_id = lst["id"]
                break

        if not list_id:
            return build_response(data={"error": f"List not found: {list_name}"})

        result = await client.call(
            "rtm.lists.archive",
            require_timeline=True,
            list_id=list_id,
        )

        lst = result.get("list", {})

        return build_response(
            data={
                "list": format_list(lst),
                "message": f"Archived list: {list_name}",
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def unarchive_list(
        ctx: Context,
        list_name: str,
    ) -> dict[str, Any]:
        """Unarchive a list.

        Args:
            list_name: Name of the list to unarchive

        Returns:
            Updated list details
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        # Need to include archived lists in search
        lists_result = await client.call("rtm.lists.getList")
        lists = parse_lists_response(lists_result)

        list_id = None
        for lst in lists:
            if lst["name"].lower() == list_name.lower():
                list_id = lst["id"]
                break

        if not list_id:
            return build_response(data={"error": f"List not found: {list_name}"})

        result = await client.call(
            "rtm.lists.unarchive",
            require_timeline=True,
            list_id=list_id,
        )

        lst = result.get("list", {})

        return build_response(
            data={
                "list": format_list(lst),
                "message": f"Unarchived list: {list_name}",
            },
            transaction_id=get_transaction_id(result),
        )

    @mcp.tool()
    async def set_default_list(
        ctx: Context,
        list_name: str,
    ) -> dict[str, Any]:
        """Set the default list for new tasks.

        Args:
            list_name: Name of the list to set as default

        Returns:
            Confirmation message
        """
        from ..client import RTMClient

        client: RTMClient = await get_client()

        lists_result = await client.call("rtm.lists.getList")
        lists = parse_lists_response(lists_result)

        list_id = None
        for lst in lists:
            if lst["name"].lower() == list_name.lower():
                list_id = lst["id"]
                break

        if not list_id:
            return build_response(data={"error": f"List not found: {list_name}"})

        await client.call(
            "rtm.lists.setDefaultList",
            require_timeline=True,
            list_id=list_id,
        )

        return build_response(
            data={"message": f"Default list set to: {list_name}"},
        )
