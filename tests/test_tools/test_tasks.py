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
