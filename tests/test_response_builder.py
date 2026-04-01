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


    def test_parse_write_response_format(self) -> None:
        """Test parsing write operation response (list at top level, not under tasks)."""
        result = {
            "stat": "ok",
            "transaction": {"id": "12345", "undoable": "1"},
            "list": {
                "id": "1",
                "taskseries": {
                    "id": "10",
                    "name": "Created Task",
                    "parent_task_id": "100",
                    "tags": {"tag": "test"},
                    "notes": [],
                    "task": {"id": "200", "priority": "N"},
                },
            },
        }

        tasks = parse_tasks_response(result)
        assert len(tasks) == 1
        assert tasks[0]["name"] == "Created Task"
        assert tasks[0]["parent_task_id"] == "100"
        assert tasks[0]["list_id"] == "1"

    def test_parse_parent_task_id_empty_string(self) -> None:
        """Test that empty parent_task_id (top-level task) is normalised to None."""
        result = {
            "stat": "ok",
            "tasks": {
                "list": {
                    "id": "1",
                    "taskseries": {
                        "id": "10",
                        "name": "Top Level Task",
                        "parent_task_id": "",
                        "tags": [],
                        "notes": [],
                        "task": {"id": "100", "priority": "N"},
                    },
                }
            },
        }

        tasks = parse_tasks_response(result)
        assert len(tasks) == 1
        assert tasks[0]["parent_task_id"] is None

    def test_parse_parent_task_id_populated(self) -> None:
        """Test that a populated parent_task_id is preserved."""
        result = {
            "stat": "ok",
            "tasks": {
                "list": {
                    "id": "1",
                    "taskseries": {
                        "id": "20",
                        "name": "Child Task",
                        "parent_task_id": "100",
                        "tags": [],
                        "notes": [],
                        "task": {"id": "200", "priority": "N"},
                    },
                }
            },
        }

        tasks = parse_tasks_response(result)
        assert len(tasks) == 1
        assert tasks[0]["parent_task_id"] == "100"

    def test_parse_parent_task_id_absent(self) -> None:
        """Test that missing parent_task_id key defaults to None."""
        result = {
            "stat": "ok",
            "tasks": {
                "list": {
                    "id": "1",
                    "taskseries": {
                        "id": "30",
                        "name": "Legacy Task",
                        "tags": [],
                        "notes": [],
                        "task": {"id": "300", "priority": "N"},
                    },
                }
            },
        }

        tasks = parse_tasks_response(result)
        assert len(tasks) == 1
        assert tasks[0]["parent_task_id"] is None

    def test_parse_parent_and_subtasks_as_siblings(self) -> None:
        """Test that parent and subtasks in the same list are all parsed with correct parent_task_id."""
        result = {
            "stat": "ok",
            "tasks": {
                "list": {
                    "id": "1",
                    "taskseries": [
                        {
                            "id": "10",
                            "name": "Parent Project",
                            "parent_task_id": "",
                            "tags": [],
                            "notes": [],
                            "task": {"id": "100", "priority": "1"},
                        },
                        {
                            "id": "20",
                            "name": "Child Alpha",
                            "parent_task_id": "100",
                            "tags": [],
                            "notes": [],
                            "task": {"id": "200", "priority": "N"},
                        },
                        {
                            "id": "30",
                            "name": "Child Beta",
                            "parent_task_id": "100",
                            "tags": [],
                            "notes": [],
                            "task": {"id": "300", "priority": "N"},
                        },
                    ],
                }
            },
        }

        tasks = parse_tasks_response(result)
        assert len(tasks) == 3

        parent = next(t for t in tasks if t["name"] == "Parent Project")
        alpha = next(t for t in tasks if t["name"] == "Child Alpha")
        beta = next(t for t in tasks if t["name"] == "Child Beta")

        assert parent["parent_task_id"] is None
        assert alpha["parent_task_id"] == "100"
        assert beta["parent_task_id"] == "100"


    def test_parse_subtasks_across_different_lists(self) -> None:
        """Test subtasks that ended up in different lists than the parent."""
        result = {
            "stat": "ok",
            "tasks": {
                "list": [
                    {
                        "id": "1",
                        "taskseries": {
                            "id": "10",
                            "name": "Parent Task",
                            "parent_task_id": "",
                            "tags": [],
                            "notes": [],
                            "task": {"id": "100", "priority": "1"},
                        },
                    },
                    {
                        "id": "2",
                        "taskseries": {
                            "id": "20",
                            "name": "Child In Other List",
                            "parent_task_id": "100",
                            "tags": [],
                            "notes": [],
                            "task": {"id": "200", "priority": "N"},
                        },
                    },
                ]
            },
        }

        tasks = parse_tasks_response(result)
        assert len(tasks) == 2
        parent = next(t for t in tasks if t["name"] == "Parent Task")
        child = next(t for t in tasks if t["name"] == "Child In Other List")
        assert parent["list_id"] == "1"
        assert child["list_id"] == "2"
        assert child["parent_task_id"] == "100"

    def test_parse_recurring_task_multiple_instances(self) -> None:
        """Test recurring task with multiple task elements in one taskseries."""
        result = {
            "stat": "ok",
            "tasks": {
                "list": {
                    "id": "1",
                    "taskseries": {
                        "id": "10",
                        "name": "Weekly Review",
                        "parent_task_id": "",
                        "tags": {"tag": "recurring"},
                        "notes": [],
                        "task": [
                            {"id": "100", "due": "2026-03-31T00:00:00Z", "priority": "N",
                             "completed": "2026-03-31T10:00:00Z"},
                            {"id": "101", "due": "2026-04-07T00:00:00Z", "priority": "N",
                             "completed": ""},
                        ],
                    },
                }
            },
        }

        tasks = parse_tasks_response(result)
        assert len(tasks) == 2
        assert tasks[0]["id"] == "100"
        assert tasks[1]["id"] == "101"
        # Both share the same taskseries metadata
        assert tasks[0]["taskseries_id"] == "10"
        assert tasks[1]["taskseries_id"] == "10"
        assert tasks[0]["name"] == "Weekly Review"
        assert tasks[1]["name"] == "Weekly Review"
        assert tasks[0]["tags"] == ["recurring"]

    def test_parse_subtask_with_full_metadata(self) -> None:
        """Test that subtasks preserve all metadata fields identically to top-level tasks."""
        result = {
            "stat": "ok",
            "tasks": {
                "list": {
                    "id": "1",
                    "taskseries": {
                        "id": "20",
                        "name": "Child With Metadata",
                        "parent_task_id": "100",
                        "url": "https://example.com",
                        "location_id": "loc123",
                        "created": "2026-03-29T11:00:00Z",
                        "modified": "2026-03-30T09:00:00Z",
                        "tags": {"tag": ["action", "urgent"]},
                        "notes": {"note": {"id": "n1", "title": "Note", "$t": "Details"}},
                        "task": {
                            "id": "200",
                            "due": "2026-04-10T00:00:00Z",
                            "has_due_time": "1",
                            "start": "2026-04-05T00:00:00Z",
                            "has_start_time": "0",
                            "completed": "",
                            "deleted": "",
                            "priority": "1",
                            "postponed": "2",
                            "estimate": "PT2H",
                        },
                    },
                }
            },
        }

        tasks = parse_tasks_response(result)
        assert len(tasks) == 1
        t = tasks[0]
        assert t["parent_task_id"] == "100"
        assert t["name"] == "Child With Metadata"
        assert t["priority"] == "1"
        assert t["due"] == "2026-04-10T00:00:00Z"
        assert t["has_due_time"] is True
        assert t["start"] == "2026-04-05T00:00:00Z"
        assert t["estimate"] == "PT2H"
        assert t["postponed"] == 2
        assert t["tags"] == ["action", "urgent"]
        assert len(t["notes"]) == 1
        assert t["url"] == "https://example.com"
        assert t["location_id"] == "loc123"

    def test_parse_write_response_empty_list(self) -> None:
        """Test write response with no taskseries (edge case)."""
        result = {
            "stat": "ok",
            "transaction": {"id": "12345", "undoable": "1"},
            "list": {"id": "1"},
        }

        tasks = parse_tasks_response(result)
        assert tasks == []

    def test_parse_write_response_cleared_parent(self) -> None:
        """Test set_parent_task response where parent was cleared (promoted to top-level)."""
        result = {
            "stat": "ok",
            "transaction": {"id": "12345", "undoable": "1"},
            "list": {
                "id": "1",
                "taskseries": {
                    "id": "20",
                    "name": "Promoted Task",
                    "parent_task_id": "",
                    "tags": [],
                    "notes": [],
                    "task": {"id": "200", "priority": "N"},
                },
            },
        }

        tasks = parse_tasks_response(result)
        assert len(tasks) == 1
        assert tasks[0]["parent_task_id"] is None


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

    def test_format_task_subtask_count(self) -> None:
        """Test that subtask_count is included in formatted output."""
        task = {
            "id": "100",
            "taskseries_id": "10",
            "list_id": "1",
            "name": "Parent Task",
            "priority": "N",
            "due": None,
            "completed": None,
            "tags": [],
            "url": None,
            "notes": [],
            "subtask_count": 3,
        }

        formatted = format_task(task)
        assert formatted["subtask_count"] == 3

    def test_format_task_subtask_count_default(self) -> None:
        """Test that subtask_count defaults to 0."""
        task = {
            "id": "100",
            "taskseries_id": "10",
            "list_id": "1",
            "name": "Task",
            "priority": "N",
            "due": None,
            "completed": None,
            "tags": [],
            "url": None,
            "notes": [],
        }

        formatted = format_task(task)
        assert formatted["subtask_count"] == 0

    def test_format_task_with_parent_task_id(self) -> None:
        """Test that parent_task_id is included in formatted output."""
        task = {
            "id": "200",
            "taskseries_id": "20",
            "list_id": "1",
            "name": "Child Task",
            "priority": "N",
            "due": None,
            "completed": None,
            "tags": [],
            "url": None,
            "notes": [],
            "parent_task_id": "100",
        }

        formatted = format_task(task)
        assert formatted["parent_task_id"] == "100"

    def test_format_task_without_parent_task_id(self) -> None:
        """Test that parent_task_id is None for top-level tasks."""
        task = {
            "id": "100",
            "taskseries_id": "10",
            "list_id": "1",
            "name": "Top Level Task",
            "priority": "N",
            "due": None,
            "completed": None,
            "tags": [],
            "url": None,
            "notes": [],
        }

        formatted = format_task(task)
        assert formatted["parent_task_id"] is None

    def test_format_mid_level_task(self) -> None:
        """Test a task that is both a child and a parent (mid-level in hierarchy)."""
        task = {
            "id": "200",
            "taskseries_id": "20",
            "list_id": "1",
            "name": "Mid-Level Task",
            "priority": "2",
            "due": None,
            "completed": None,
            "tags": ["project"],
            "url": None,
            "notes": [],
            "parent_task_id": "100",
            "subtask_count": 3,
        }

        formatted = format_task(task)
        assert formatted["parent_task_id"] == "100"
        assert formatted["subtask_count"] == 3

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
