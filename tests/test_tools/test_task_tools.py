"""Tests for task MCP tools via mocked RTM client."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

# ---------------------------------------------------------------------------
# Helpers: build realistic RTM API responses
# ---------------------------------------------------------------------------

def _make_getlist_response(
    taskseries_list: list[dict] | dict,
    list_id: str = "1",
) -> dict[str, Any]:
    """Build a rtm.tasks.getList-style response."""
    return {
        "stat": "ok",
        "tasks": {
            "list": {
                "id": list_id,
                "taskseries": taskseries_list,
            }
        },
    }


def _make_write_response(
    taskseries: dict,
    list_id: str = "1",
    transaction_id: str = "tx999",
    undoable: str = "1",
) -> dict[str, Any]:
    """Build a write-operation (add/complete/set*) response."""
    return {
        "stat": "ok",
        "transaction": {"id": transaction_id, "undoable": undoable},
        "list": {
            "id": list_id,
            "taskseries": taskseries,
        },
    }


def _ts(
    ts_id: str = "10",
    task_id: str = "100",
    name: str = "Test Task",
    parent_task_id: str = "",
    priority: str = "N",
    tags: list[str] | None = None,
    completed: str = "",
    due: str = "",
    estimate: str = "",
) -> dict[str, Any]:
    """Build a minimal taskseries dict."""
    tag_data: Any = []
    if tags:
        tag_data = {"tag": tags if len(tags) > 1 else tags[0]}
    return {
        "id": ts_id,
        "created": "2026-01-01T00:00:00Z",
        "modified": "2026-01-01T00:00:00Z",
        "name": name,
        "source": "api",
        "url": "",
        "location_id": "",
        "parent_task_id": parent_task_id,
        "tags": tag_data,
        "participants": [],
        "notes": [],
        "task": {
            "id": task_id,
            "due": due,
            "has_due_time": "0",
            "added": "2026-01-01T00:00:00Z",
            "completed": completed,
            "deleted": "",
            "priority": priority,
            "postponed": "0",
            "estimate": estimate,
            "start": "",
            "has_start_time": "0",
        },
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    """Create a mock RTMClient whose .call() can be configured per-test."""
    client = AsyncMock()
    client.call = AsyncMock()
    return client


@pytest.fixture
def _patch_settings(mock_client):
    """Make _get_user_timezone return None (skip settings call)."""
    # We configure the mock in each test; this fixture is a reminder that
    # settings calls must be accounted for when the tool calls _get_user_timezone.
    pass


# ---------------------------------------------------------------------------
# Helper to set up sequential mock responses
# ---------------------------------------------------------------------------

def _setup_calls(mock_client, responses: list[dict]):
    """Configure mock_client.call to return responses in order."""
    mock_client.call = AsyncMock(side_effect=responses)


def _setup_call_map(mock_client, method_map: dict[str, Any]):
    """Configure mock_client.call to return responses based on method name."""
    async def _side_effect(method, **kwargs):
        if method in method_map:
            val = method_map[method]
            return val() if callable(val) else val
        raise ValueError(f"Unexpected method: {method}")
    mock_client.call = AsyncMock(side_effect=_side_effect)


# ---------------------------------------------------------------------------
# We test tools by importing register_task_tools and calling the registered
# functions directly through a minimal FastMCP-like object.
# ---------------------------------------------------------------------------

class FakeMCP:
    """Minimal stand-in for FastMCP that captures registered tools."""

    def __init__(self):
        self.tools: dict[str, Any] = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


class FakeContext:
    """Minimal stand-in for fastmcp.Context."""
    pass


@pytest.fixture
def task_tools(mock_client):
    """Register task tools and return (tools_dict, mock_client)."""
    from rtm_mcp.tools.tasks import register_task_tools

    fake_mcp = FakeMCP()

    async def get_client():
        return mock_client

    register_task_tools(fake_mcp, get_client)
    return fake_mcp.tools, mock_client


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------

class TestListTasks:
    """Test list_tasks tool."""

    @pytest.mark.asyncio
    async def test_basic_list(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        getlist_resp = _make_getlist_response([
            _ts(name="Task A", priority="1"),
            _ts(ts_id="20", task_id="200", name="Task B"),
        ])
        _setup_calls(client, [getlist_resp, settings_resp])

        result = await tools["list_tasks"](FakeContext())
        assert result["data"]["count"] == 2
        names = [t["name"] for t in result["data"]["tasks"]]
        assert "Task A" in names
        assert "Task B" in names

    @pytest.mark.asyncio
    async def test_filters_completed_by_default(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        getlist_resp = _make_getlist_response([
            _ts(name="Open Task"),
            _ts(ts_id="20", task_id="200", name="Done Task",
                completed="2026-03-30T10:00:00Z"),
        ])
        _setup_calls(client, [getlist_resp, settings_resp])

        result = await tools["list_tasks"](FakeContext())
        assert result["data"]["count"] == 1
        assert result["data"]["tasks"][0]["name"] == "Open Task"

    @pytest.mark.asyncio
    async def test_include_completed(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        getlist_resp = _make_getlist_response([
            _ts(name="Open"),
            _ts(ts_id="20", task_id="200", name="Done",
                completed="2026-03-30T10:00:00Z"),
        ])
        _setup_calls(client, [getlist_resp, settings_resp])

        result = await tools["list_tasks"](FakeContext(), include_completed=True)
        assert result["data"]["count"] == 2

    @pytest.mark.asyncio
    async def test_parent_task_id_filter(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        getlist_resp = _make_getlist_response([
            _ts(name="Child A", parent_task_id="100"),
            _ts(ts_id="20", task_id="200", name="Child B", parent_task_id="100"),
            _ts(ts_id="30", task_id="300", name="Other Child", parent_task_id="999"),
        ])
        _setup_calls(client, [getlist_resp, settings_resp])

        result = await tools["list_tasks"](FakeContext(), parent_task_id="100")
        assert result["data"]["count"] == 2
        names = [t["name"] for t in result["data"]["tasks"]]
        assert "Child A" in names
        assert "Child B" in names
        assert "Other Child" not in names

    @pytest.mark.asyncio
    async def test_parent_task_id_injects_issubtask_filter(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        getlist_resp = _make_getlist_response([])
        _setup_calls(client, [getlist_resp, settings_resp])

        await tools["list_tasks"](FakeContext(), parent_task_id="100")

        # Verify the API call included isSubtask:true
        call_args = client.call.call_args_list[0]
        assert "isSubtask:true" in call_args.kwargs.get("filter", "")

    @pytest.mark.asyncio
    async def test_subtask_count_computed(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        getlist_resp = _make_getlist_response([
            _ts(name="Parent", task_id="100"),
            _ts(ts_id="20", task_id="200", name="Child A", parent_task_id="100"),
            _ts(ts_id="30", task_id="300", name="Child B", parent_task_id="100"),
        ])
        _setup_calls(client, [getlist_resp, settings_resp])

        result = await tools["list_tasks"](FakeContext())
        parent = next(t for t in result["data"]["tasks"] if t["name"] == "Parent")
        child = next(t for t in result["data"]["tasks"] if t["name"] == "Child A")
        assert parent["subtask_count"] == 2
        assert child["subtask_count"] == 0

    @pytest.mark.asyncio
    async def test_empty_result(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        getlist_resp = {"stat": "ok", "tasks": {}}
        _setup_calls(client, [getlist_resp, settings_resp])

        result = await tools["list_tasks"](FakeContext())
        assert result["data"]["count"] == 0
        assert result["data"]["tasks"] == []

    @pytest.mark.asyncio
    async def test_list_name_filter(self, task_tools):
        tools, client = task_tools
        lists_resp = {
            "stat": "ok",
            "lists": {
                "list": [
                    {"id": "5", "name": "Work", "deleted": "0", "locked": "0",
                     "archived": "0", "position": "0", "smart": "0"},
                ]
            },
        }
        getlist_resp = _make_getlist_response([_ts(name="Work Task")], list_id="5")
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        _setup_calls(client, [getlist_resp, lists_resp, getlist_resp, settings_resp])

        # We need list lookup then task fetch, but the tool calls getList first
        # then lists. Let me use call_map instead.
        async def _side(method, **kw):
            # First call is getList for tasks, second is getLists, etc.
            if method == "rtm.lists.getList":
                return lists_resp
            if method == "rtm.settings.getList":
                return settings_resp
            return getlist_resp

        client.call = AsyncMock(side_effect=_side)

        result = await tools["list_tasks"](FakeContext(), list_name="Work")
        assert result["data"]["count"] == 1

        # Verify list_id was passed
        task_call = next(c for c in client.call.call_args_list
                        if c.args[0] == "rtm.tasks.getList")
        assert task_call.kwargs.get("list_id") == "5"


# ---------------------------------------------------------------------------
# add_task
# ---------------------------------------------------------------------------

class TestAddTask:
    """Test add_task tool."""

    @pytest.mark.asyncio
    async def test_basic_add(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        add_resp = _make_write_response(
            _ts(name="New Task"), transaction_id="tx123",
        )
        _setup_calls(client, [add_resp, settings_resp])

        result = await tools["add_task"](FakeContext(), name="New Task")
        assert result["data"]["task"]["name"] == "New Task"
        assert result["metadata"]["transaction_id"] == "tx123"

    @pytest.mark.asyncio
    async def test_add_with_parent_task_id(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        add_resp = _make_write_response(
            _ts(name="Child", parent_task_id="100"),
        )
        _setup_calls(client, [add_resp, settings_resp])

        result = await tools["add_task"](
            FakeContext(), name="Child", parent_task_id="100",
        )
        assert result["data"]["task"]["parent_task_id"] == "100"

        # Verify parent_task_id was passed to API
        call_kw = client.call.call_args_list[0].kwargs
        assert call_kw["parent_task_id"] == "100"

    @pytest.mark.asyncio
    async def test_add_with_external_id(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        add_resp = _make_write_response(_ts(name="Linked Task"))
        _setup_calls(client, [add_resp, settings_resp])

        result = await tools["add_task"](
            FakeContext(), name="Linked Task", external_id="JIRA-1234",
        )
        assert result["data"]["task"]["name"] == "Linked Task"

        # Verify external_id was passed to API
        call_kw = client.call.call_args_list[0].kwargs
        assert call_kw["external_id"] == "JIRA-1234"

    @pytest.mark.asyncio
    async def test_add_with_list_name(self, task_tools):
        tools, client = task_tools
        lists_resp = {
            "stat": "ok",
            "lists": {
                "list": {"id": "5", "name": "Work", "deleted": "0",
                         "locked": "0", "archived": "0", "position": "0",
                         "smart": "0"},
            },
        }
        add_resp = _make_write_response(_ts(name="Work Task"), list_id="5")
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}

        async def _side(method, **kw):
            if method == "rtm.lists.getList":
                return lists_resp
            if method == "rtm.settings.getList":
                return settings_resp
            return add_resp

        client.call = AsyncMock(side_effect=_side)

        result = await tools["add_task"](
            FakeContext(), name="Work Task", list_name="Work",
        )
        assert result["data"]["task"]["name"] == "Work Task"

    @pytest.mark.asyncio
    async def test_add_without_parse(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        add_resp = _make_write_response(_ts(name="Literal #tag"))
        _setup_calls(client, [add_resp, settings_resp])

        await tools["add_task"](FakeContext(), name="Literal #tag", parse=False)

        call_kw = client.call.call_args_list[0].kwargs
        assert call_kw["parse"] == "0"


# ---------------------------------------------------------------------------
# complete_task / uncomplete_task
# ---------------------------------------------------------------------------

class TestCompleteTask:
    """Test complete_task and uncomplete_task tools."""

    @pytest.mark.asyncio
    async def test_complete_by_name(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([_ts(name="My Task")])
        complete_resp = _make_write_response(
            _ts(name="My Task", completed="2026-04-01T10:00:00Z"),
            transaction_id="tx456",
        )
        _setup_calls(client, [find_resp, complete_resp, settings_resp])

        result = await tools["complete_task"](FakeContext(), task_name="My Task")
        assert "Completed" in result["data"]["message"]
        assert result["metadata"]["transaction_id"] == "tx456"

    @pytest.mark.asyncio
    async def test_complete_by_ids(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        complete_resp = _make_write_response(
            _ts(name="Task"), transaction_id="tx789",
        )
        _setup_calls(client, [complete_resp, settings_resp])

        result = await tools["complete_task"](
            FakeContext(), task_id="100", taskseries_id="10", list_id="1",
        )
        assert result["metadata"]["transaction_id"] == "tx789"

    @pytest.mark.asyncio
    async def test_complete_not_found(self, task_tools):
        tools, client = task_tools
        find_resp = {"stat": "ok", "tasks": {}}
        _setup_calls(client, [find_resp])

        result = await tools["complete_task"](FakeContext(), task_name="Nope")
        assert "error" in result["data"]

    @pytest.mark.asyncio
    async def test_complete_missing_ids(self, task_tools):
        tools, _client = task_tools

        result = await tools["complete_task"](FakeContext(), task_id="100")
        assert "error" in result["data"]

    @pytest.mark.asyncio
    async def test_uncomplete_by_name(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([
            _ts(name="Done Task", completed="2026-03-30T10:00:00Z"),
        ])
        uncomplete_resp = _make_write_response(
            _ts(name="Done Task"), transaction_id="tx101",
        )
        _setup_calls(client, [find_resp, uncomplete_resp, settings_resp])

        result = await tools["uncomplete_task"](FakeContext(), task_name="Done Task")
        assert "Reopened" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_uncomplete_task_not_completed(self, task_tools):
        tools, client = task_tools
        find_resp = _make_getlist_response([_ts(name="Open Task")])
        _setup_calls(client, [find_resp])

        result = await tools["uncomplete_task"](FakeContext(), task_name="Open Task")
        assert "not completed" in result["data"]["error"]


# ---------------------------------------------------------------------------
# delete_task
# ---------------------------------------------------------------------------

class TestDeleteTask:
    """Test delete_task tool."""

    @pytest.mark.asyncio
    async def test_delete_by_name(self, task_tools):
        tools, client = task_tools
        find_resp = _make_getlist_response([_ts(name="Trash Me")])
        delete_resp = _make_write_response(_ts(name="Trash Me"), transaction_id="txdel")
        _setup_calls(client, [find_resp, delete_resp])

        result = await tools["delete_task"](FakeContext(), task_name="Trash Me")
        assert "Deleted" in result["data"]["message"]
        assert result["metadata"]["transaction_id"] == "txdel"

    @pytest.mark.asyncio
    async def test_delete_not_found(self, task_tools):
        tools, client = task_tools
        find_resp = {"stat": "ok", "tasks": {}}
        _setup_calls(client, [find_resp])

        result = await tools["delete_task"](FakeContext(), task_name="Ghost")
        assert "error" in result["data"]


# ---------------------------------------------------------------------------
# set_task_* tools
# ---------------------------------------------------------------------------

class TestSetTaskProperties:
    """Test set_task_name, set_task_due_date, set_task_priority, etc."""

    @pytest.mark.asyncio
    async def test_set_name(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([_ts(name="Old Name")])
        rename_resp = _make_write_response(_ts(name="New Name"), transaction_id="txr")
        _setup_calls(client, [find_resp, rename_resp, settings_resp])

        result = await tools["set_task_name"](
            FakeContext(), new_name="New Name", task_name="Old Name",
        )
        assert result["data"]["task"]["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_set_due_date(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([_ts(name="Task")])
        due_resp = _make_write_response(
            _ts(name="Task", due="2026-04-15T00:00:00Z"),
        )
        _setup_calls(client, [find_resp, due_resp, settings_resp])

        result = await tools["set_task_due_date"](
            FakeContext(), due="April 15", task_name="Task",
        )
        assert result["data"]["task"]["due"] is not None

    @pytest.mark.asyncio
    async def test_clear_due_date(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([_ts(name="Task")])
        due_resp = _make_write_response(_ts(name="Task"))
        _setup_calls(client, [find_resp, due_resp, settings_resp])

        result = await tools["set_task_due_date"](
            FakeContext(), due="", task_name="Task",
        )
        assert "cleared" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_set_priority(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([_ts(name="Task")])
        prio_resp = _make_write_response(_ts(name="Task", priority="1"))
        _setup_calls(client, [find_resp, prio_resp, settings_resp])

        result = await tools["set_task_priority"](
            FakeContext(), priority="high", task_name="Task",
        )
        assert result["data"]["task"]["priority"] == "high"

    @pytest.mark.asyncio
    async def test_set_estimate(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([_ts(name="Task")])
        est_resp = _make_write_response(_ts(name="Task", estimate="PT2H"))
        _setup_calls(client, [find_resp, est_resp, settings_resp])

        result = await tools["set_task_estimate"](
            FakeContext(), estimate="2 hours", task_name="Task",
        )
        assert result["data"]["task"]["estimate"] == "PT2H"

    @pytest.mark.asyncio
    async def test_set_url(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([_ts(name="Task")])
        url_resp = _make_write_response(_ts(name="Task"))
        _setup_calls(client, [find_resp, url_resp, settings_resp])

        result = await tools["set_task_url"](
            FakeContext(), url="https://example.com", task_name="Task",
        )
        assert "URL set" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_set_start_date(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([_ts(name="Task")])
        start_resp = _make_write_response(_ts(name="Task"))
        _setup_calls(client, [find_resp, start_resp, settings_resp])

        result = await tools["set_task_start_date"](
            FakeContext(), start="next monday", task_name="Task",
        )
        assert "Start date set" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_set_recurrence(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([_ts(name="Task")])
        rec_resp = _make_write_response(_ts(name="Task"))
        _setup_calls(client, [find_resp, rec_resp, settings_resp])

        result = await tools["set_task_recurrence"](
            FakeContext(), repeat="every week", task_name="Task",
        )
        assert "Recurrence set" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_task_not_found(self, task_tools):
        """All set_task_* tools return error when task not found."""
        tools, client = task_tools
        find_resp = {"stat": "ok", "tasks": {}}
        _setup_calls(client, [find_resp])

        result = await tools["set_task_name"](
            FakeContext(), new_name="X", task_name="Ghost",
        )
        assert "error" in result["data"]


# ---------------------------------------------------------------------------
# Tag tools
# ---------------------------------------------------------------------------

class TestTagTools:
    """Test add_task_tags, remove_task_tags, set_task_tags."""

    @pytest.mark.asyncio
    async def test_add_tags(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([_ts(name="Task", tags=["existing"])])
        tag_resp = _make_write_response(
            _ts(name="Task", tags=["existing", "new"]),
        )
        _setup_calls(client, [find_resp, tag_resp, settings_resp])

        result = await tools["add_task_tags"](
            FakeContext(), tags="new", task_name="Task",
        )
        assert "Added tags" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_remove_tags(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([_ts(name="Task", tags=["a", "b"])])
        tag_resp = _make_write_response(_ts(name="Task", tags=["a"]))
        _setup_calls(client, [find_resp, tag_resp, settings_resp])

        result = await tools["remove_task_tags"](
            FakeContext(), tags="b", task_name="Task",
        )
        assert "Removed tags" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_set_tags_replace_all(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([_ts(name="Task", tags=["old"])])
        tag_resp = _make_write_response(
            _ts(name="Task", tags=["new1", "new2"]),
        )
        _setup_calls(client, [find_resp, tag_resp, settings_resp])

        result = await tools["set_task_tags"](
            FakeContext(), tags="new1,new2", task_name="Task",
        )
        assert "Tags set to" in result["data"]["message"]
        assert "new1" in result["data"]["task"]["tags"]

    @pytest.mark.asyncio
    async def test_set_tags_clear_all(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([_ts(name="Task", tags=["old"])])
        tag_resp = _make_write_response(_ts(name="Task"))
        _setup_calls(client, [find_resp, tag_resp, settings_resp])

        result = await tools["set_task_tags"](
            FakeContext(), tags="", task_name="Task",
        )
        assert "cleared" in result["data"]["message"]


# ---------------------------------------------------------------------------
# move_task_priority
# ---------------------------------------------------------------------------

class TestMoveTaskPriority:
    """Test move_task_priority tool."""

    @pytest.mark.asyncio
    async def test_move_up(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([_ts(name="Task", priority="N")])
        move_resp = _make_write_response(_ts(name="Task", priority="3"))
        _setup_calls(client, [find_resp, move_resp, settings_resp])

        result = await tools["move_task_priority"](
            FakeContext(), direction="up", task_name="Task",
        )
        assert result["data"]["task"]["priority"] == "low"
        assert "moved up" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_move_down(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([_ts(name="Task", priority="1")])
        move_resp = _make_write_response(_ts(name="Task", priority="2"))
        _setup_calls(client, [find_resp, move_resp, settings_resp])

        result = await tools["move_task_priority"](
            FakeContext(), direction="down", task_name="Task",
        )
        assert result["data"]["task"]["priority"] == "medium"

    @pytest.mark.asyncio
    async def test_invalid_direction(self, task_tools):
        tools, _client = task_tools

        result = await tools["move_task_priority"](
            FakeContext(), direction="sideways", task_name="Task",
        )
        assert "error" in result["data"]
        assert "Invalid direction" in result["data"]["error"]


# ---------------------------------------------------------------------------
# postpone_task
# ---------------------------------------------------------------------------

class TestPostponeTask:
    """Test postpone_task tool."""

    @pytest.mark.asyncio
    async def test_postpone(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([
            _ts(name="Task", due="2026-04-01T00:00:00Z"),
        ])
        postpone_resp = _make_write_response(
            _ts(name="Task", due="2026-04-02T00:00:00Z"),
        )
        _setup_calls(client, [find_resp, postpone_resp, settings_resp])

        result = await tools["postpone_task"](FakeContext(), task_name="Task")
        assert "postponed" in result["data"]["message"]


# ---------------------------------------------------------------------------
# move_task
# ---------------------------------------------------------------------------

class TestMoveTask:
    """Test move_task tool."""

    @pytest.mark.asyncio
    async def test_move_to_list(self, task_tools):
        tools, client = task_tools
        lists_resp = {
            "stat": "ok",
            "lists": {
                "list": [
                    {"id": "1", "name": "Inbox", "deleted": "0", "locked": "0",
                     "archived": "0", "position": "0", "smart": "0"},
                    {"id": "5", "name": "Work", "deleted": "0", "locked": "0",
                     "archived": "0", "position": "1", "smart": "0"},
                ]
            },
        }
        find_resp = _make_getlist_response([_ts(name="Task")])
        move_resp = _make_write_response(_ts(name="Task"), list_id="5")
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}

        async def _side(method, **kw):
            if method == "rtm.lists.getList":
                return lists_resp
            if method == "rtm.settings.getList":
                return settings_resp
            if method == "rtm.tasks.moveTo":
                return move_resp
            return find_resp

        client.call = AsyncMock(side_effect=_side)

        result = await tools["move_task"](
            FakeContext(), to_list_name="Work", task_name="Task",
        )
        assert "Moved to" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_move_to_nonexistent_list(self, task_tools):
        tools, client = task_tools
        lists_resp = {
            "stat": "ok",
            "lists": {"list": {"id": "1", "name": "Inbox", "deleted": "0",
                               "locked": "0", "archived": "0", "position": "0",
                               "smart": "0"}},
        }

        async def _side(method, **kw):
            return lists_resp

        client.call = AsyncMock(side_effect=_side)

        result = await tools["move_task"](
            FakeContext(), to_list_name="Nonexistent", task_name="Task",
        )
        assert "error" in result["data"]


# ---------------------------------------------------------------------------
# set_parent_task
# ---------------------------------------------------------------------------

class TestSetParentTask:
    """Test set_parent_task tool."""

    @pytest.mark.asyncio
    async def test_reparent_task(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([_ts(name="Child")])
        set_resp = _make_write_response(
            _ts(name="Child", parent_task_id="500"),
            transaction_id="txp",
        )
        _setup_calls(client, [find_resp, set_resp, settings_resp])

        result = await tools["set_parent_task"](
            FakeContext(), task_name="Child", parent_task_id="500",
        )
        assert result["data"]["task"]["parent_task_id"] == "500"
        assert "parent task 500" in result["data"]["message"]
        assert result["metadata"]["transaction_id"] == "txp"

    @pytest.mark.asyncio
    async def test_promote_to_top_level(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([
            _ts(name="Child", parent_task_id="500"),
        ])
        set_resp = _make_write_response(_ts(name="Child"))
        _setup_calls(client, [find_resp, set_resp, settings_resp])

        result = await tools["set_parent_task"](
            FakeContext(), task_name="Child",
        )
        assert result["data"]["task"]["parent_task_id"] is None
        assert "top-level" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_set_parent_passes_parent_id_to_api(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([_ts(name="Task")])
        set_resp = _make_write_response(_ts(name="Task", parent_task_id="500"))
        _setup_calls(client, [find_resp, set_resp, settings_resp])

        await tools["set_parent_task"](
            FakeContext(), task_name="Task", parent_task_id="500",
        )

        set_call = client.call.call_args_list[1]
        assert set_call.args[0] == "rtm.tasks.setParentTask"
        assert set_call.kwargs["parent_task_id"] == "500"

    @pytest.mark.asyncio
    async def test_set_parent_not_found(self, task_tools):
        tools, client = task_tools
        find_resp = {"stat": "ok", "tasks": {}}
        _setup_calls(client, [find_resp])

        result = await tools["set_parent_task"](
            FakeContext(), task_name="Ghost",
        )
        assert "error" in result["data"]

    @pytest.mark.asyncio
    async def test_promote_omits_parent_id_from_api(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([_ts(name="Task")])
        set_resp = _make_write_response(_ts(name="Task"))
        _setup_calls(client, [find_resp, set_resp, settings_resp])

        await tools["set_parent_task"](FakeContext(), task_name="Task")

        set_call = client.call.call_args_list[1]
        assert "parent_task_id" not in set_call.kwargs


# ---------------------------------------------------------------------------
# Smart list filter handling
# ---------------------------------------------------------------------------

class TestSmartListFilter:
    """Test that smart list filters are applied correctly."""

    @pytest.mark.asyncio
    async def test_smart_list_uses_filter_not_list_id(self, task_tools):
        tools, client = task_tools
        lists_resp = {
            "stat": "ok",
            "lists": {
                "list": {
                    "id": "99", "name": "Due Today", "deleted": "0",
                    "locked": "0", "archived": "0", "position": "0",
                    "smart": "1", "filter": "dueBefore:tomorrow",
                },
            },
        }
        getlist_resp = _make_getlist_response([_ts(name="Urgent")])
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}

        async def _side(method, **kw):
            if method == "rtm.lists.getList":
                return lists_resp
            if method == "rtm.settings.getList":
                return settings_resp
            return getlist_resp

        client.call = AsyncMock(side_effect=_side)

        await tools["list_tasks"](FakeContext(), list_name="Due Today")

        # Should NOT pass list_id for smart lists — should merge the filter
        task_call = next(c for c in client.call.call_args_list
                        if c.args[0] == "rtm.tasks.getList")
        assert "list_id" not in task_call.kwargs
        assert "dueBefore:tomorrow" in task_call.kwargs.get("filter", "")

    @pytest.mark.asyncio
    async def test_smart_list_normalises_nbsp(self, task_tools):
        """Smart list filters may contain non-breaking spaces (U+00A0)."""
        tools, client = task_tools
        lists_resp = {
            "stat": "ok",
            "lists": {
                "list": {
                    "id": "99", "name": "My Smart", "deleted": "0",
                    "locked": "0", "archived": "0", "position": "0",
                    "smart": "1", "filter": "tag:work\xa0AND\xa0priority:1",
                },
            },
        }
        getlist_resp = _make_getlist_response([_ts(name="Task")])
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}

        async def _side(method, **kw):
            if method == "rtm.lists.getList":
                return lists_resp
            if method == "rtm.settings.getList":
                return settings_resp
            return getlist_resp

        client.call = AsyncMock(side_effect=_side)

        await tools["list_tasks"](FakeContext(), list_name="My Smart")

        task_call = next(c for c in client.call.call_args_list
                        if c.args[0] == "rtm.tasks.getList")
        filt = task_call.kwargs.get("filter", "")
        # Non-breaking spaces should be replaced with regular spaces
        assert "\xa0" not in filt
        assert "tag:work AND priority:1" in filt


# ---------------------------------------------------------------------------
# _find_task: partial name matching
# ---------------------------------------------------------------------------

class TestFindTask:
    """Test _find_task helper for exact and partial matching."""

    @pytest.mark.asyncio
    async def test_exact_match_preferred(self, task_tools):
        """Exact match should be preferred over partial match."""
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        # Two tasks: one exact match, one partial
        find_resp = _make_getlist_response([
            _ts(ts_id="10", task_id="100", name="Buy milk"),
            _ts(ts_id="20", task_id="200", name="Buy milk and eggs"),
        ])
        complete_resp = _make_write_response(
            _ts(name="Buy milk", completed="2026-04-01T10:00:00Z"),
        )
        _setup_calls(client, [find_resp, complete_resp, settings_resp])

        await tools["complete_task"](FakeContext(), task_name="Buy milk")
        # Should have used the exact match (task_id 100)
        complete_call = client.call.call_args_list[1]
        assert complete_call.kwargs["task_id"] == "100"

    @pytest.mark.asyncio
    async def test_partial_match_fallback(self, task_tools):
        """Falls back to partial match when no exact match exists."""
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([
            _ts(ts_id="20", task_id="200", name="Buy milk and eggs"),
        ])
        complete_resp = _make_write_response(
            _ts(name="Buy milk and eggs", completed="2026-04-01T10:00:00Z"),
        )
        _setup_calls(client, [find_resp, complete_resp, settings_resp])

        await tools["complete_task"](FakeContext(), task_name="milk")
        # Should have found via partial match
        complete_call = client.call.call_args_list[1]
        assert complete_call.kwargs["task_id"] == "200"

    @pytest.mark.asyncio
    async def test_case_insensitive_match(self, task_tools):
        tools, client = task_tools
        settings_resp = {"stat": "ok", "settings": {"timezone": "UTC"}}
        find_resp = _make_getlist_response([
            _ts(name="Buy Milk"),
        ])
        complete_resp = _make_write_response(
            _ts(name="Buy Milk", completed="2026-04-01T10:00:00Z"),
        )
        _setup_calls(client, [find_resp, complete_resp, settings_resp])

        result = await tools["complete_task"](FakeContext(), task_name="buy milk")
        assert "Completed" in result["data"]["message"]


# ---------------------------------------------------------------------------
# _parse_estimate_minutes
# ---------------------------------------------------------------------------

class TestParseEstimateMinutes:
    """Test estimate string parsing."""

    def test_iso_hours(self):
        from rtm_mcp.tools.tasks import _parse_estimate_minutes
        assert _parse_estimate_minutes("PT1H") == 60
        assert _parse_estimate_minutes("PT2H") == 120

    def test_iso_minutes(self):
        from rtm_mcp.tools.tasks import _parse_estimate_minutes
        assert _parse_estimate_minutes("PT30M") == 30
        assert _parse_estimate_minutes("PT45M") == 45

    def test_iso_hours_and_minutes(self):
        from rtm_mcp.tools.tasks import _parse_estimate_minutes
        assert _parse_estimate_minutes("PT1H30M") == 90
        assert _parse_estimate_minutes("PT2H15M") == 135

    def test_human_readable(self):
        from rtm_mcp.tools.tasks import _parse_estimate_minutes
        assert _parse_estimate_minutes("1 hour") == 60
        assert _parse_estimate_minutes("30 minutes") == 30
        assert _parse_estimate_minutes("2 hours 30 minutes") == 150

    def test_empty_and_none(self):
        from rtm_mcp.tools.tasks import _parse_estimate_minutes
        assert _parse_estimate_minutes(None) is None
        assert _parse_estimate_minutes("") is None

    def test_unparseable(self):
        from rtm_mcp.tools.tasks import _parse_estimate_minutes
        assert _parse_estimate_minutes("soon") is None
        assert _parse_estimate_minutes("a while") is None


# ---------------------------------------------------------------------------
# _resolve_task_ids
# ---------------------------------------------------------------------------

class TestResolveTaskIds:
    """Test task ID resolution."""

    @pytest.mark.asyncio
    async def test_with_direct_ids(self):
        from rtm_mcp.tools.tasks import _resolve_task_ids
        mock_client = AsyncMock()

        result = await _resolve_task_ids(
            mock_client, None, "100", "10", "1",
        )
        assert result == {"task_id": "100", "taskseries_id": "10", "list_id": "1"}
        # Should NOT have called the API
        mock_client.call.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_partial_ids(self):
        from rtm_mcp.tools.tasks import _resolve_task_ids
        mock_client = AsyncMock()

        result = await _resolve_task_ids(
            mock_client, None, "100", None, None,
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_name_lookup(self):
        from rtm_mcp.tools.tasks import _resolve_task_ids
        mock_client = AsyncMock()
        mock_client.call.return_value = _make_getlist_response([
            _ts(ts_id="10", task_id="100", name="My Task"),
        ])

        result = await _resolve_task_ids(
            mock_client, "My Task", None, None, None,
        )
        assert result == {"task_id": "100", "taskseries_id": "10", "list_id": "1"}

    @pytest.mark.asyncio
    async def test_name_not_found(self):
        from rtm_mcp.tools.tasks import _resolve_task_ids
        mock_client = AsyncMock()
        mock_client.call.return_value = {"stat": "ok", "tasks": {}}

        result = await _resolve_task_ids(
            mock_client, "Ghost", None, None, None,
        )
        assert "error" in result
