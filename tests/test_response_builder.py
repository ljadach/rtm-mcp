"""Tests for response builder."""

from rtm_mcp.response_builder import (
    build_response,
    format_list,
    format_task,
    parse_lists_response,
    parse_tasks_response,
    priority_to_code,
)


class TestBuildResponse:
    """Test response building."""

    def test_basic_response(self) -> None:
        """Test basic response structure."""
        result = build_response(data={"key": "value"})

        assert "data" in result
        assert "metadata" in result
        assert result["data"]["key"] == "value"
        assert "fetched_at" in result["metadata"]

    def test_with_analysis(self) -> None:
        """Test response with analysis."""
        result = build_response(
            data={"key": "value"},
            analysis={"insights": ["test insight"]},
        )

        assert "analysis" in result
        assert result["analysis"]["insights"] == ["test insight"]

    def test_with_transaction_id(self) -> None:
        """Test response with transaction ID."""
        result = build_response(
            data={"key": "value"},
            transaction_id="tx123",
        )

        assert result["metadata"]["transaction_id"] == "tx123"


class TestPriorityConversion:
    """Test priority code conversion."""

    def test_number_priorities(self) -> None:
        """Test numeric priority conversion."""
        assert priority_to_code(1) == "1"
        assert priority_to_code(2) == "2"
        assert priority_to_code(3) == "3"
        assert priority_to_code(0) == "N"

    def test_string_priorities(self) -> None:
        """Test string priority conversion."""
        assert priority_to_code("high") == "1"
        assert priority_to_code("medium") == "2"
        assert priority_to_code("low") == "3"
        assert priority_to_code("none") == "N"
        assert priority_to_code("N") == "N"

    def test_case_insensitive(self) -> None:
        """Test case insensitivity."""
        assert priority_to_code("HIGH") == "1"
        assert priority_to_code("Medium") == "2"

    def test_none_value(self) -> None:
        """Test None handling."""
        assert priority_to_code(None) == "N"


class TestParseTasksResponse:
    """Test task response parsing."""

    def test_parse_single_task(self, sample_task_response: dict) -> None:
        """Test parsing single task."""
        tasks = parse_tasks_response(sample_task_response)

        assert len(tasks) == 1
        task = tasks[0]

        assert task["id"] == "789"
        assert task["taskseries_id"] == "456"
        assert task["list_id"] == "123"
        assert task["name"] == "Test Task"
        assert task["priority"] == "1"
        assert task["tags"] == ["work", "urgent"]

    def test_parse_empty_response(self) -> None:
        """Test parsing empty response."""
        result = {"stat": "ok", "tasks": {}}
        tasks = parse_tasks_response(result)

        assert tasks == []

    def test_parse_multiple_lists(self) -> None:
        """Test parsing tasks from multiple lists."""
        result = {
            "stat": "ok",
            "tasks": {
                "list": [
                    {
                        "id": "1",
                        "taskseries": {
                            "id": "10",
                            "name": "Task 1",
                            "tags": [],
                            "notes": [],
                            "task": {"id": "100", "priority": "N"},
                        },
                    },
                    {
                        "id": "2",
                        "taskseries": {
                            "id": "20",
                            "name": "Task 2",
                            "tags": [],
                            "notes": [],
                            "task": {"id": "200", "priority": "2"},
                        },
                    },
                ]
            },
        }

        tasks = parse_tasks_response(result)
        assert len(tasks) == 2
        assert tasks[0]["list_id"] == "1"
        assert tasks[1]["list_id"] == "2"


class TestParseListsResponse:
    """Test list response parsing."""

    def test_parse_lists(self, sample_lists_response: dict) -> None:
        """Test parsing lists."""
        lists = parse_lists_response(sample_lists_response)

        assert len(lists) == 3
        assert lists[0]["name"] == "Inbox"
        assert lists[0]["locked"] is True
        assert lists[1]["name"] == "Personal"
        assert lists[2]["name"] == "Work"

    def test_parse_single_list(self) -> None:
        """Test parsing single list (dict instead of list)."""
        result = {
            "stat": "ok",
            "lists": {
                "list": {
                    "id": "1",
                    "name": "Only List",
                    "deleted": "0",
                    "locked": "0",
                    "archived": "0",
                    "position": "0",
                    "smart": "0",
                }
            },
        }

        lists = parse_lists_response(result)
        assert len(lists) == 1
        assert lists[0]["name"] == "Only List"


class TestFormatTask:
    """Test task formatting."""

    def test_format_basic_task(self) -> None:
        """Test basic task formatting."""
        task = {
            "id": "123",
            "taskseries_id": "456",
            "list_id": "789",
            "name": "Test Task",
            "priority": "1",
            "due": "2024-01-15T00:00:00Z",
            "completed": None,
            "tags": ["work"],
            "url": None,
            "notes": [],
        }

        formatted = format_task(task)

        assert formatted["name"] == "Test Task"
        assert formatted["priority"] == "high"
        assert formatted["id"] == "123"

    def test_format_without_ids(self) -> None:
        """Test formatting without IDs."""
        task = {
            "id": "123",
            "taskseries_id": "456",
            "list_id": "789",
            "name": "Test",
            "priority": "N",
            "due": None,
            "completed": None,
            "tags": [],
            "url": None,
            "notes": [],
        }

        formatted = format_task(task, include_ids=False)

        assert "id" not in formatted
        assert "taskseries_id" not in formatted


class TestFormatList:
    """Test list formatting."""

    def test_format_list(self) -> None:
        """Test list formatting."""
        lst = {
            "id": "123",
            "name": "Test List",
            "smart": "0",
            "archived": "0",
            "locked": "1",
        }

        formatted = format_list(lst)

        assert formatted["id"] == "123"
        assert formatted["name"] == "Test List"
        assert formatted["smart"] is False
        assert formatted["locked"] is True
