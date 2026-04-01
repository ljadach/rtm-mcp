"""Tests for list MCP tools via mocked RTM client."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest


class FakeMCP:
    def __init__(self):
        self.tools: dict[str, Any] = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


class FakeContext:
    pass


def _lists_response(lists: list[dict]) -> dict[str, Any]:
    """Build a rtm.lists.getList response."""
    return {
        "stat": "ok",
        "lists": {"list": lists if len(lists) != 1 else lists[0]},
    }


def _list_entry(
    id: str = "1",
    name: str = "Inbox",
    deleted: str = "0",
    locked: str = "0",
    archived: str = "0",
    position: str = "0",
    smart: str = "0",
) -> dict[str, Any]:
    return {
        "id": id, "name": name, "deleted": deleted, "locked": locked,
        "archived": archived, "position": position, "smart": smart,
    }


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.call = AsyncMock()
    client.record_transaction = MagicMock()
    type(client).timeline_id = PropertyMock(return_value="tl_test")
    return client


@pytest.fixture
def list_tools(mock_client):
    mcp = FakeMCP()
    from rtm_mcp.tools.lists import register_list_tools

    async def get_client():
        return mock_client

    register_list_tools(mcp, get_client)
    return mcp.tools, mock_client


# ---------------------------------------------------------------------------
# get_lists
# ---------------------------------------------------------------------------

class TestGetLists:
    @pytest.mark.asyncio
    async def test_basic(self, list_tools):
        tools, client = list_tools
        client.call = AsyncMock(return_value=_lists_response([
            _list_entry(id="1", name="Inbox", position="0"),
            _list_entry(id="2", name="Work", position="1"),
        ]))

        result = await tools["get_lists"](FakeContext())
        assert result["data"]["count"] == 2
        # Sorted by position
        assert result["data"]["lists"][0]["name"] == "Inbox"

    @pytest.mark.asyncio
    async def test_excludes_archived_by_default(self, list_tools):
        tools, client = list_tools
        client.call = AsyncMock(return_value=_lists_response([
            _list_entry(id="1", name="Active"),
            _list_entry(id="2", name="Old", archived="1"),
        ]))

        result = await tools["get_lists"](FakeContext())
        assert result["data"]["count"] == 1
        assert result["data"]["lists"][0]["name"] == "Active"

    @pytest.mark.asyncio
    async def test_include_archived(self, list_tools):
        tools, client = list_tools
        client.call = AsyncMock(return_value=_lists_response([
            _list_entry(id="1", name="Active"),
            _list_entry(id="2", name="Old", archived="1"),
        ]))

        result = await tools["get_lists"](FakeContext(), include_archived=True)
        assert result["data"]["count"] == 2

    @pytest.mark.asyncio
    async def test_exclude_smart(self, list_tools):
        tools, client = list_tools
        client.call = AsyncMock(return_value=_lists_response([
            _list_entry(id="1", name="Normal"),
            _list_entry(id="2", name="Due Today", smart="1"),
        ]))

        result = await tools["get_lists"](FakeContext(), include_smart=False)
        assert result["data"]["count"] == 1
        assert result["data"]["lists"][0]["name"] == "Normal"


# ---------------------------------------------------------------------------
# add_list
# ---------------------------------------------------------------------------

class TestAddList:
    @pytest.mark.asyncio
    async def test_basic(self, list_tools):
        tools, client = list_tools
        client.call = AsyncMock(return_value={
            "stat": "ok",
            "transaction": {"id": "tx1", "undoable": "1"},
            "list": _list_entry(id="99", name="New List"),
        })

        result = await tools["add_list"](FakeContext(), name="New List")
        assert result["data"]["message"] == "Created list: New List"
        assert result["metadata"]["transaction_id"] == "tx1"

    @pytest.mark.asyncio
    async def test_smart_list(self, list_tools):
        tools, client = list_tools
        client.call = AsyncMock(return_value={
            "stat": "ok",
            "transaction": {"id": "tx2", "undoable": "1"},
            "list": {**_list_entry(id="99", name="Urgent", smart="1"), "filter": "priority:1"},
        })

        await tools["add_list"](
            FakeContext(), name="Urgent", filter="priority:1",
        )
        # Verify filter was passed to API
        call_kwargs = client.call.call_args.kwargs
        assert call_kwargs["filter"] == "priority:1"


# ---------------------------------------------------------------------------
# rename_list
# ---------------------------------------------------------------------------

class TestRenameList:
    @pytest.mark.asyncio
    async def test_rename(self, list_tools):
        tools, client = list_tools

        async def _side(method, **kw):
            if method == "rtm.lists.getList":
                return _lists_response([_list_entry(id="5", name="Old Name")])
            return {
                "stat": "ok",
                "transaction": {"id": "tx3", "undoable": "1"},
                "list": _list_entry(id="5", name="New Name"),
            }

        client.call = AsyncMock(side_effect=_side)

        result = await tools["rename_list"](
            FakeContext(), list_name="Old Name", new_name="New Name",
        )
        assert "Renamed" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_not_found(self, list_tools):
        tools, client = list_tools
        client.call = AsyncMock(return_value=_lists_response([
            _list_entry(id="1", name="Other"),
        ]))

        result = await tools["rename_list"](
            FakeContext(), list_name="Missing", new_name="X",
        )
        assert "error" in result["data"]


# ---------------------------------------------------------------------------
# delete_list
# ---------------------------------------------------------------------------

class TestDeleteList:
    @pytest.mark.asyncio
    async def test_delete(self, list_tools):
        tools, client = list_tools

        async def _side(method, **kw):
            if method == "rtm.lists.getList":
                return _lists_response([_list_entry(id="5", name="Trash")])
            return {"stat": "ok", "transaction": {"id": "tx4", "undoable": "1"}}

        client.call = AsyncMock(side_effect=_side)

        result = await tools["delete_list"](FakeContext(), list_name="Trash")
        assert "Deleted" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_locked_list(self, list_tools):
        tools, client = list_tools
        client.call = AsyncMock(return_value=_lists_response([
            _list_entry(id="1", name="Inbox", locked="1"),
        ]))

        result = await tools["delete_list"](FakeContext(), list_name="Inbox")
        assert "locked" in result["data"]["error"].lower()

    @pytest.mark.asyncio
    async def test_not_found(self, list_tools):
        tools, client = list_tools
        client.call = AsyncMock(return_value=_lists_response([
            _list_entry(id="1", name="Other"),
        ]))

        result = await tools["delete_list"](FakeContext(), list_name="Missing")
        assert "error" in result["data"]


# ---------------------------------------------------------------------------
# archive_list / unarchive_list
# ---------------------------------------------------------------------------

class TestArchiveList:
    @pytest.mark.asyncio
    async def test_archive(self, list_tools):
        tools, client = list_tools

        async def _side(method, **kw):
            if method == "rtm.lists.getList":
                return _lists_response([_list_entry(id="5", name="Old")])
            return {
                "stat": "ok",
                "transaction": {"id": "tx5", "undoable": "1"},
                "list": _list_entry(id="5", name="Old", archived="1"),
            }

        client.call = AsyncMock(side_effect=_side)

        result = await tools["archive_list"](FakeContext(), list_name="Old")
        assert "Archived" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_archive_not_found(self, list_tools):
        tools, client = list_tools
        client.call = AsyncMock(return_value=_lists_response([
            _list_entry(name="Other"),
        ]))

        result = await tools["archive_list"](FakeContext(), list_name="Missing")
        assert "error" in result["data"]


class TestUnarchiveList:
    @pytest.mark.asyncio
    async def test_unarchive(self, list_tools):
        tools, client = list_tools

        async def _side(method, **kw):
            if method == "rtm.lists.getList":
                return _lists_response([_list_entry(id="5", name="Old", archived="1")])
            return {
                "stat": "ok",
                "transaction": {"id": "tx6", "undoable": "1"},
                "list": _list_entry(id="5", name="Old", archived="0"),
            }

        client.call = AsyncMock(side_effect=_side)

        result = await tools["unarchive_list"](FakeContext(), list_name="Old")
        assert "Unarchived" in result["data"]["message"]


# ---------------------------------------------------------------------------
# set_default_list
# ---------------------------------------------------------------------------

class TestSetDefaultList:
    @pytest.mark.asyncio
    async def test_set_default(self, list_tools):
        tools, client = list_tools

        async def _side(method, **kw):
            if method == "rtm.lists.getList":
                return _lists_response([_list_entry(id="5", name="Personal")])
            return {"stat": "ok"}

        client.call = AsyncMock(side_effect=_side)

        result = await tools["set_default_list"](FakeContext(), list_name="Personal")
        assert "Default list set" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_not_found(self, list_tools):
        tools, client = list_tools
        client.call = AsyncMock(return_value=_lists_response([
            _list_entry(name="Other"),
        ]))

        result = await tools["set_default_list"](FakeContext(), list_name="Missing")
        assert "error" in result["data"]
