"""Tests for RTM exception hierarchy and error code mapping."""

import pytest

from rtm_mcp.exceptions import (
    ERROR_CODE_MAP,
    RTMAuthError,
    RTMError,
    RTMNotFoundError,
    RTMValidationError,
    raise_for_error,
)


class TestRaiseForError:
    """Test raise_for_error maps codes to the correct exception class."""

    @pytest.mark.parametrize(
        "code,expected_cls",
        [
            (98, RTMAuthError),
            (99, RTMAuthError),
            (114, RTMAuthError),
            (100, RTMValidationError),
            (101, RTMValidationError),
            (112, RTMValidationError),
            (340, RTMNotFoundError),
            (341, RTMNotFoundError),
        ],
    )
    def test_mapped_codes(self, code: int, expected_cls: type) -> None:
        with pytest.raises(expected_cls) as exc_info:
            raise_for_error(code, f"error {code}")
        assert exc_info.value.code == code
        assert f"error {code}" in exc_info.value.message

    def test_unmapped_code_raises_base(self) -> None:
        with pytest.raises(RTMError) as exc_info:
            raise_for_error(9999, "unknown")
        assert exc_info.value.code == 9999

    @pytest.mark.parametrize(
        "code,msg",
        [
            (4040, "Sub-task editing requires a RTM Pro account"),
            (4050, "Invalid parent_task_id"),
            (4060, "Sub-tasks nested too deep"),
            (4070, "Cannot make repeating task a subtask of repeating task"),
            (4090, "Task cannot be its own parent"),
        ],
    )
    def test_subtask_error_codes(self, code: int, msg: str) -> None:
        with pytest.raises(RTMValidationError) as exc_info:
            raise_for_error(code, msg)
        assert exc_info.value.code == code
        assert msg in exc_info.value.message


class TestErrorCodeMapCompleteness:
    """Verify ERROR_CODE_MAP contains expected entries."""

    def test_all_subtask_codes_mapped(self) -> None:
        subtask_codes = {4040, 4050, 4060, 4070, 4080, 4090}
        assert subtask_codes.issubset(ERROR_CODE_MAP.keys())

    def test_all_values_are_rtm_error_subclasses(self) -> None:
        for code, cls in ERROR_CODE_MAP.items():
            assert issubclass(cls, RTMError), f"Code {code} maps to {cls}"
