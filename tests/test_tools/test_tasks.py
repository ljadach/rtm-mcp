"""Tests for task tools."""

# These tests verify the helper functions used by task tools

from rtm_mcp.tools.tasks import _apply_subtask_counts


class TestApplySubtaskCounts:
    """Test subtask count computation."""

    def test_parent_with_children(self) -> None:
        """Test that parent gets correct subtask_count from children in result set."""
        tasks = [
            {"id": "100", "name": "Parent", "parent_task_id": None},
            {"id": "200", "name": "Child A", "parent_task_id": "100"},
            {"id": "300", "name": "Child B", "parent_task_id": "100"},
        ]
        _apply_subtask_counts(tasks)
        assert tasks[0]["subtask_count"] == 2
        assert tasks[1]["subtask_count"] == 0
        assert tasks[2]["subtask_count"] == 0

    def test_parent_without_children_in_set(self) -> None:
        """Test that parent has subtask_count=0 when children are not in result set."""
        tasks = [
            {"id": "100", "name": "Parent", "parent_task_id": None},
        ]
        _apply_subtask_counts(tasks)
        assert tasks[0]["subtask_count"] == 0

    def test_children_without_parent_in_set(self) -> None:
        """Test that orphan children don't increment counts on missing parents."""
        tasks = [
            {"id": "200", "name": "Child A", "parent_task_id": "100"},
            {"id": "300", "name": "Child B", "parent_task_id": "100"},
        ]
        _apply_subtask_counts(tasks)
        assert tasks[0]["subtask_count"] == 0
        assert tasks[1]["subtask_count"] == 0

    def test_empty_list(self) -> None:
        """Test with empty task list."""
        tasks: list[dict] = []
        _apply_subtask_counts(tasks)
        assert tasks == []

    def test_no_hierarchy(self) -> None:
        """Test with tasks that have no parent-child relationships."""
        tasks = [
            {"id": "100", "name": "Task A", "parent_task_id": None},
            {"id": "200", "name": "Task B", "parent_task_id": None},
        ]
        _apply_subtask_counts(tasks)
        assert tasks[0]["subtask_count"] == 0
        assert tasks[1]["subtask_count"] == 0

    def test_nested_hierarchy(self) -> None:
        """Test three levels: grandparent → parent → child."""
        tasks = [
            {"id": "100", "name": "Grandparent", "parent_task_id": None},
            {"id": "200", "name": "Parent", "parent_task_id": "100"},
            {"id": "300", "name": "Child", "parent_task_id": "200"},
        ]
        _apply_subtask_counts(tasks)
        assert tasks[0]["subtask_count"] == 1  # Parent is its child
        assert tasks[1]["subtask_count"] == 1  # Child is its child
        assert tasks[2]["subtask_count"] == 0


    def test_multiple_parents_with_different_children(self) -> None:
        """Test multiple independent parent-child groups in one result set."""
        tasks = [
            {"id": "100", "name": "Project A", "parent_task_id": None},
            {"id": "200", "name": "A - Task 1", "parent_task_id": "100"},
            {"id": "300", "name": "A - Task 2", "parent_task_id": "100"},
            {"id": "400", "name": "Project B", "parent_task_id": None},
            {"id": "500", "name": "B - Task 1", "parent_task_id": "400"},
        ]
        _apply_subtask_counts(tasks)

        proj_a = next(t for t in tasks if t["id"] == "100")
        proj_b = next(t for t in tasks if t["id"] == "400")
        assert proj_a["subtask_count"] == 2
        assert proj_b["subtask_count"] == 1

    def test_mid_level_task_is_both_child_and_parent(self) -> None:
        """A task that is both a subtask of a grandparent AND has its own children."""
        tasks = [
            {"id": "100", "name": "Grandparent", "parent_task_id": None},
            {"id": "200", "name": "Mid-level", "parent_task_id": "100"},
            {"id": "300", "name": "Leaf A", "parent_task_id": "200"},
            {"id": "400", "name": "Leaf B", "parent_task_id": "200"},
        ]
        _apply_subtask_counts(tasks)

        grandparent = next(t for t in tasks if t["id"] == "100")
        mid = next(t for t in tasks if t["id"] == "200")
        leaf_a = next(t for t in tasks if t["id"] == "300")

        assert grandparent["subtask_count"] == 1  # Mid-level
        assert mid["subtask_count"] == 2  # Leaf A + Leaf B
        assert leaf_a["subtask_count"] == 0

    def test_count_reflects_incomplete_children_only(self) -> None:
        """Simulate list_tasks default: completed children are filtered out before counting."""
        all_tasks = [
            {"id": "100", "name": "Parent", "parent_task_id": None, "completed": None},
            {"id": "200", "name": "Child A", "parent_task_id": "100", "completed": None},
            {"id": "300", "name": "Child B", "parent_task_id": "100", "completed": "2026-03-30T10:00:00Z"},
        ]
        # Simulate the incomplete filter applied in list_tasks
        tasks = [t for t in all_tasks if not t.get("completed")]
        _apply_subtask_counts(tasks)

        parent = next(t for t in tasks if t["id"] == "100")
        assert parent["subtask_count"] == 1  # Only Child A (incomplete)

    def test_count_zero_when_all_children_completed(self) -> None:
        """When all children are completed and filtered out, parent subtask_count is 0."""
        all_tasks = [
            {"id": "100", "name": "Parent", "parent_task_id": None, "completed": None},
            {"id": "200", "name": "Child A", "parent_task_id": "100", "completed": "2026-03-30T10:00:00Z"},
            {"id": "300", "name": "Child B", "parent_task_id": "100", "completed": "2026-03-30T11:00:00Z"},
        ]
        tasks = [t for t in all_tasks if not t.get("completed")]
        _apply_subtask_counts(tasks)

        parent = next(t for t in tasks if t["id"] == "100")
        assert parent["subtask_count"] == 0

    def test_count_with_include_completed(self) -> None:
        """Simulate include_completed=True: all children counted regardless of status."""
        tasks = [
            {"id": "100", "name": "Parent", "parent_task_id": None, "completed": None},
            {"id": "200", "name": "Child A", "parent_task_id": "100", "completed": None},
            {"id": "300", "name": "Child B", "parent_task_id": "100", "completed": "2026-03-30T10:00:00Z"},
        ]
        # No completion filter — simulates include_completed=True
        _apply_subtask_counts(tasks)

        parent = next(t for t in tasks if t["id"] == "100")
        assert parent["subtask_count"] == 2

    def test_count_progressive_completion(self) -> None:
        """Simulate subtasks being completed one by one."""
        parent = {"id": "100", "name": "Parent", "parent_task_id": None, "completed": None}
        child_a = {"id": "200", "name": "Child A", "parent_task_id": "100", "completed": None}
        child_b = {"id": "300", "name": "Child B", "parent_task_id": "100", "completed": None}
        child_c = {"id": "400", "name": "Child C", "parent_task_id": "100", "completed": None}

        # All incomplete
        tasks = [t for t in [parent, child_a, child_b, child_c] if not t.get("completed")]
        _apply_subtask_counts(tasks)
        assert parent["subtask_count"] == 3

        # Complete one
        child_a["completed"] = "2026-04-01T09:00:00Z"
        tasks = [t for t in [parent, child_a, child_b, child_c] if not t.get("completed")]
        _apply_subtask_counts(tasks)
        assert parent["subtask_count"] == 2

        # Complete another
        child_b["completed"] = "2026-04-01T10:00:00Z"
        tasks = [t for t in [parent, child_a, child_b, child_c] if not t.get("completed")]
        _apply_subtask_counts(tasks)
        assert parent["subtask_count"] == 1

        # Complete last
        child_c["completed"] = "2026-04-01T11:00:00Z"
        tasks = [t for t in [parent, child_a, child_b, child_c] if not t.get("completed")]
        _apply_subtask_counts(tasks)
        assert parent["subtask_count"] == 0


class TestTaskAnalysis:
    """Test task analysis functionality."""

    def test_analyze_empty_tasks(self) -> None:
        """Test analysis of empty task list."""
        from rtm_mcp.tools.tasks import _analyze_tasks

        result = _analyze_tasks([])
        assert result == {}

    def test_analyze_tasks_with_priorities(self) -> None:
        """Test priority counting."""
        from rtm_mcp.tools.tasks import _analyze_tasks

        tasks = [
            {"priority": "1", "due": None, "tags": []},
            {"priority": "1", "due": None, "tags": []},
            {"priority": "2", "due": None, "tags": ["work"]},
            {"priority": "N", "due": None, "tags": []},
        ]

        result = _analyze_tasks(tasks)

        assert result["summary"]["total"] == 4
        assert result["summary"]["by_priority"]["high"] == 2
        assert result["summary"]["by_priority"]["medium"] == 1
        assert result["summary"]["by_priority"]["none"] == 1
        assert "work" in result["tags_used"]

    def test_analyze_overdue_tasks(self) -> None:
        """Test overdue task detection."""
        from rtm_mcp.tools.tasks import _analyze_tasks

        tasks = [
            {"priority": "N", "due": "2020-01-01T00:00:00Z", "tags": []},  # Overdue
            {"priority": "N", "due": "2099-12-31T00:00:00Z", "tags": []},  # Future
        ]

        result = _analyze_tasks(tasks)

        assert result["summary"]["overdue"] == 1

    def test_analyze_tasks_with_timezone(self) -> None:
        """Test that timezone is properly applied for date comparisons."""
        from datetime import UTC, datetime
        from zoneinfo import ZoneInfo

        from rtm_mcp.tools.tasks import _analyze_tasks

        # Create a task due "today" in a specific timezone
        # Use a timezone that's ahead of UTC (e.g., Europe/Warsaw = UTC+1 or UTC+2)
        test_tz = ZoneInfo("Europe/Warsaw")
        now_local = datetime.now(test_tz)
        today_local = now_local.date()

        # Create a due date at midnight local time, converted to UTC
        due_midnight_local = datetime(
            today_local.year, today_local.month, today_local.day, 0, 0, 0, tzinfo=test_tz
        )
        due_utc = due_midnight_local.astimezone(UTC)

        tasks = [
            {
                "priority": "N",
                "due": due_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "tags": [],
            },
        ]

        # With correct timezone, task should be "due today"
        result = _analyze_tasks(tasks, timezone="Europe/Warsaw")
        assert result["summary"]["due_today"] == 1
        assert result["summary"]["overdue"] == 0

    def test_analyze_tasks_timezone_overdue(self) -> None:
        """Test that overdue detection works correctly with timezone."""
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo

        from rtm_mcp.tools.tasks import _analyze_tasks

        # Create a task that was due yesterday in the user's timezone
        test_tz = ZoneInfo("Europe/Warsaw")
        now_local = datetime.now(test_tz)
        yesterday_local = (now_local - timedelta(days=1)).date()

        # Due at noon yesterday local time
        due_yesterday = datetime(
            yesterday_local.year,
            yesterday_local.month,
            yesterday_local.day,
            12,
            0,
            0,
            tzinfo=test_tz,
        )
        due_utc = due_yesterday.astimezone(ZoneInfo("UTC"))

        tasks = [
            {
                "priority": "N",
                "due": due_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "tags": [],
            },
        ]

        result = _analyze_tasks(tasks, timezone="Europe/Warsaw")
        assert result["summary"]["overdue"] == 1
        assert result["summary"]["due_today"] == 0
