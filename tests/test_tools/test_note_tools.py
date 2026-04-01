"""Tests for note MCP tools via mocked RTM client."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_getlist_response(
    taskseries_list: list[dict] | dict,
    list_id: str = "1",
) -> dict[str, Any]:
    return {
        "stat": "ok",
        "tasks": {"list": {"id": list_id, "taskseries": taskseries_list}},
    }


def _ts(
    ts_id: str = "10",
    task_id: str = "100",
    name: str = "Test Task",
    notes: Any = None,
) -> dict[str, Any]:
    return {
        "id": ts_id,
        "created": "2026-01-01T00:00:00Z",
        "modified": "2026-01-01T00:00:00Z",
        "name": name,
        "source": "api",
        "url": "",
        "location_id": "",
        "parent_task_id": "",
        "tags": [],
        "participants": [],
        "notes": notes if notes is not None else [],
        "task": {
            "id": task_id,
            "due": "",
            "has_due_time": "0",
            "added": "2026-01-01T00:00:00Z",
            "completed": "",
            "deleted": "",
            "priority": "N",
            "postponed": "0",
            "estimate": "",
            "start": "",
            "has_start_time": "0",
        },
    }


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


@pytest.fixture
def note_tools(mock_client):
    mcp = FakeMCP()
    from rtm_mcp.tools.notes import register_note_tools

    async def get_client():
        return mock_client

    register_note_tools(mcp, get_client)
    return mcp.tools, mock_client


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.call = AsyncMock()
    client.record_transaction = MagicMock()
    type(client).timeline_id = PropertyMock(return_value="tl_test")
    return client


# ---------------------------------------------------------------------------
# Tests: add_note
# ---------------------------------------------------------------------------

class TestAddNote:
    @pytest.mark.asyncio
    async def test_add_note_by_ids(self, note_tools):
        tools, client = note_tools
        add_resp = {
            "stat": "ok",
            "transaction": {"id": "tx1", "undoable": "1"},
            "note": {
                "id": "n1",
                "title": "My Title",
                "$t": "Note body",
                "created": "2026-01-01T00:00:00Z",
            },
        }
        client.call = AsyncMock(return_value=add_resp)

        result = await tools["add_note"](
            FakeContext(),
            note_text="Note body",
            note_title="My Title",
            task_id="100",
            taskseries_id="10",
            list_id="1",
        )
        assert result["data"]["note"]["id"] == "n1"
        assert result["data"]["note"]["body"] == "Note body"
        assert result["data"]["note"]["title"] == "My Title"
        assert result["metadata"]["transaction_id"] == "tx1"

    @pytest.mark.asyncio
    async def test_add_note_by_name(self, note_tools):
        tools, client = note_tools
        find_resp = _make_getlist_response([_ts(name="Buy milk")])
        add_resp = {
            "stat": "ok",
            "transaction": {"id": "tx2", "undoable": "1"},
            "note": {"id": "n2", "$t": "Remember oat milk", "created": "2026-01-01"},
        }
        client.call = AsyncMock(side_effect=[find_resp, add_resp])

        result = await tools["add_note"](
            FakeContext(), note_text="Remember oat milk", task_name="Buy milk",
        )
        assert result["data"]["message"] == "Note added"

    @pytest.mark.asyncio
    async def test_add_note_task_not_found(self, note_tools):
        tools, client = note_tools
        client.call = AsyncMock(return_value=_make_getlist_response([]))

        result = await tools["add_note"](
            FakeContext(), note_text="body", task_name="Nonexistent",
        )
        assert "error" in result["data"]

    @pytest.mark.asyncio
    async def test_add_note_missing_ids(self, note_tools):
        tools, _client = note_tools
        result = await tools["add_note"](
            FakeContext(), note_text="body", task_id="100",
        )
        assert "error" in result["data"]


# ---------------------------------------------------------------------------
# Tests: edit_note
# ---------------------------------------------------------------------------

class TestEditNote:
    @pytest.mark.asyncio
    async def test_edit_note(self, note_tools):
        tools, client = note_tools
        edit_resp = {
            "stat": "ok",
            "transaction": {"id": "tx3", "undoable": "1"},
            "note": {"id": "n1", "title": "Updated", "$t": "New body", "modified": "2026-01-02"},
        }
        client.call = AsyncMock(return_value=edit_resp)

        result = await tools["edit_note"](
            FakeContext(),
            note_id="n1",
            note_text="New body",
            note_title="Updated",
            task_id="100",
            taskseries_id="10",
            list_id="1",
        )
        assert result["data"]["note"]["body"] == "New body"
        assert result["data"]["message"] == "Note updated"

    @pytest.mark.asyncio
    async def test_edit_note_body_field_fallback(self, note_tools):
        """RTM may return 'body' instead of '$t'."""
        tools, client = note_tools
        edit_resp = {
            "stat": "ok",
            "transaction": {"id": "tx4", "undoable": "1"},
            "note": {"id": "n1", "body": "Fallback body", "modified": "2026-01-02"},
        }
        client.call = AsyncMock(return_value=edit_resp)

        result = await tools["edit_note"](
            FakeContext(), note_id="n1", note_text="Fallback body",
            task_id="100", taskseries_id="10", list_id="1",
        )
        assert result["data"]["note"]["body"] == "Fallback body"


# ---------------------------------------------------------------------------
# Tests: delete_note
# ---------------------------------------------------------------------------

class TestDeleteNote:
    @pytest.mark.asyncio
    async def test_delete_note(self, note_tools):
        tools, client = note_tools
        del_resp = {
            "stat": "ok",
            "transaction": {"id": "tx5", "undoable": "1"},
        }
        client.call = AsyncMock(return_value=del_resp)

        result = await tools["delete_note"](
            FakeContext(), note_id="n1",
            task_id="100", taskseries_id="10", list_id="1",
        )
        assert result["data"]["message"] == "Note deleted"
        assert result["metadata"]["transaction_id"] == "tx5"

    @pytest.mark.asyncio
    async def test_delete_note_task_not_found(self, note_tools):
        tools, client = note_tools
        client.call = AsyncMock(return_value=_make_getlist_response([]))

        result = await tools["delete_note"](
            FakeContext(), note_id="n1", task_name="Missing",
        )
        assert "error" in result["data"]


# ---------------------------------------------------------------------------
# Tests: get_task_notes
# ---------------------------------------------------------------------------

class TestGetTaskNotes:
    @pytest.mark.asyncio
    async def test_get_notes_by_name(self, note_tools):
        tools, client = note_tools
        notes_data = [
            {"id": "n1", "title": "Note 1", "$t": "Body 1", "created": "2026-01-01"},
            {"id": "n2", "title": "", "$t": "Body 2", "created": "2026-01-02"},
        ]
        resp = _make_getlist_response([_ts(name="My Task", notes={"note": notes_data})])
        client.call = AsyncMock(return_value=resp)

        result = await tools["get_task_notes"](FakeContext(), task_name="My Task")
        assert result["data"]["count"] == 2
        assert result["data"]["notes"][0]["body"] == "Body 1"
        assert result["data"]["task_name"] == "My Task"

    @pytest.mark.asyncio
    async def test_get_notes_by_ids(self, note_tools):
        tools, client = note_tools
        notes_data = {"id": "n1", "title": "Solo", "$t": "Content", "created": "2026-01-01"}
        resp = _make_getlist_response([_ts(notes={"note": notes_data})])
        client.call = AsyncMock(return_value=resp)

        result = await tools["get_task_notes"](
            FakeContext(), task_id="100", taskseries_id="10", list_id="1",
        )
        assert result["data"]["count"] == 1

    @pytest.mark.asyncio
    async def test_get_notes_empty(self, note_tools):
        tools, client = note_tools
        resp = _make_getlist_response([_ts(notes=[])])
        client.call = AsyncMock(return_value=resp)

        result = await tools["get_task_notes"](FakeContext(), task_name="Test Task")
        assert result["data"]["count"] == 0

    @pytest.mark.asyncio
    async def test_get_notes_task_not_found(self, note_tools):
        tools, client = note_tools
        client.call = AsyncMock(return_value=_make_getlist_response([]))

        result = await tools["get_task_notes"](FakeContext(), task_name="Nope")
        assert "error" in result["data"]

    @pytest.mark.asyncio
    async def test_get_notes_missing_ids(self, note_tools):
        tools, _client = note_tools
        result = await tools["get_task_notes"](FakeContext(), task_id="100")
        assert "error" in result["data"]

    @pytest.mark.asyncio
    async def test_get_notes_single_note_as_dict(self, note_tools):
        """RTM returns a single note as dict, not a list."""
        tools, client = note_tools
        # RTM wraps notes under {"note": {...}} for single, {"note": [...]} for multiple
        single_note = {"note": {"id": "n1", "title": "T", "$t": "B", "created": "2026-01-01"}}
        resp = _make_getlist_response([_ts(notes=single_note)])
        client.call = AsyncMock(return_value=resp)

        result = await tools["get_task_notes"](FakeContext(), task_name="Test Task")
        assert result["data"]["count"] == 1
