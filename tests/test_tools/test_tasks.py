"""Tests for task tools."""

# These tests verify the helper functions used by task tools


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
        from datetime import UTC, datetime, timedelta
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
