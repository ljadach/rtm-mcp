"""Tests for list tools."""


class TestListFiltering:
    """Test list filtering functionality."""

    def test_filter_archived_lists(self, sample_lists_response: dict) -> None:
        """Test filtering out archived lists."""
        from rtm_mcp.response_builder import parse_lists_response

        lists = parse_lists_response(sample_lists_response)

        # All should be unarchived
        unarchived = [lst for lst in lists if not lst["archived"]]
        assert len(unarchived) == 3

    def test_filter_smart_lists(self, sample_lists_response: dict) -> None:
        """Test filtering smart lists."""
        from rtm_mcp.response_builder import parse_lists_response

        lists = parse_lists_response(sample_lists_response)

        # None should be smart in sample
        non_smart = [lst for lst in lists if not lst["smart"]]
        assert len(non_smart) == 3

    def test_list_sorting(self, sample_lists_response: dict) -> None:
        """Test list sorting by position."""
        from rtm_mcp.response_builder import parse_lists_response

        lists = parse_lists_response(sample_lists_response)

        # Sort by position
        sorted_lists = sorted(
            lists,
            key=lambda x: (x["position"] if x["position"] >= 0 else 9999, x["name"]),
        )

        # Personal should come first (position 0)
        assert sorted_lists[0]["name"] == "Personal"
        # Work should come second (position 1)
        assert sorted_lists[1]["name"] == "Work"
