"""Tests for note tools."""

from typing import Any

import pytest

from rtm_mcp.tools.notes import register_note_tools


class FakeMCP:
    """Collects tool functions registered with @mcp.tool()."""

    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self) -> Any:
        def decorator(fn: Any) -> Any:
            self.tools[fn.__name__] = fn
            return fn

        return decorator


class FakeClient:
    """Records API calls and returns a fixed response."""

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call(self, method: str, **params: Any) -> dict[str, Any]:
        self.calls.append((method, params))
        return self.response


@pytest.fixture
def notes_tools(sample_task_response: dict) -> tuple[dict[str, Any], FakeClient]:
    client = FakeClient(sample_task_response)

    async def get_client() -> FakeClient:
        return client

    mcp = FakeMCP()
    register_note_tools(mcp, get_client)
    return mcp.tools, client


class TestGetTaskNotes:
    """get_task_notes must not request a whole list unfiltered.

    An unfiltered rtm.tasks.getList includes every completed task, and RTM
    can answer HTTP 502 for such a request on a list with a long history.
    """

    async def test_lookup_by_ids_filters_incomplete(self, notes_tools: tuple) -> None:
        tools, client = notes_tools

        result = await tools["get_task_notes"](
            None, task_id="789", taskseries_id="456", list_id="123"
        )

        assert result["data"]["task_name"] == "Test Task"
        assert client.calls == [
            ("rtm.tasks.getList", {"list_id": "123", "filter": "status:incomplete"})
        ]

    async def test_lookup_by_name_filters_incomplete(self, notes_tools: tuple) -> None:
        tools, client = notes_tools

        result = await tools["get_task_notes"](None, task_name="Test Task")

        assert result["data"]["task_name"] == "Test Task"
        assert client.calls == [("rtm.tasks.getList", {"filter": "status:incomplete"})]
