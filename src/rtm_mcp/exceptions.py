"""RTM MCP Exception hierarchy."""


class RTMError(Exception):
    """Base exception for RTM errors."""

    def __init__(self, message: str, code: int | None = None):
        self.message = message
        self.code = code
        super().__init__(message)


class RTMAuthError(RTMError):
    """Authentication failed or token expired."""

    pass


class RTMRateLimitError(RTMError):
    """Rate limit exceeded."""

    pass


class RTMNotFoundError(RTMError):
    """Resource not found (task, list, etc.)."""

    pass


class RTMValidationError(RTMError):
    """Invalid parameters or request."""

    pass


class RTMNetworkError(RTMError):
    """Network or connection error."""

    pass


# RTM API error code mapping
ERROR_CODE_MAP = {
    98: RTMAuthError,  # Login failed / Invalid auth token
    99: RTMAuthError,  # Insufficient permissions
    100: RTMValidationError,  # Invalid signature
    101: RTMValidationError,  # Invalid API key
    102: RTMValidationError,  # Service currently unavailable
    105: RTMValidationError,  # Service not found
    111: RTMValidationError,  # Signature missing
    112: RTMValidationError,  # Method not found
    113: RTMValidationError,  # Invalid format
    114: RTMAuthError,  # User not logged in
    340: RTMNotFoundError,  # List not found
    341: RTMNotFoundError,  # Task not found
    # Subtask / hierarchy errors
    4040: RTMValidationError,  # Sub-task editing requires Pro account
    4050: RTMValidationError,  # Invalid parent_task_id
    4060: RTMValidationError,  # Sub-tasks nested too deep (max 3 levels)
    4070: RTMValidationError,  # Repeating task cannot be parent/child of repeating task
    4080: RTMValidationError,  # Due date must be after start date
    4090: RTMValidationError,  # Task cannot be its own parent
}

# Recovery hints appended to RTM error messages so agents can self-correct.
ERROR_GUIDANCE: dict[int, str] = {
    98: "Re-run rtm-setup to get a fresh auth token.",
    99: "The token needs 'delete' permission. Re-run rtm-setup.",
    100: "Request signature is invalid. This is likely a bug — check RTM_SHARED_SECRET.",
    101: "Check RTM_API_KEY env var or ~/.config/rtm-mcp/config.json.",
    102: "RTM service is temporarily unavailable. Try again in a few minutes.",
    105: "The requested RTM API service was not found. Check the method name.",
    111: "Request signature is missing. This is likely a bug in the client.",
    112: "The RTM API method does not exist. Check the method name.",
    113: "Invalid response format requested. This is likely a bug in the client.",
    114: "User is not logged in. Re-run rtm-setup to authenticate.",
    340: "Call get_lists to see available list names.",
    341: "Call list_tasks to find the correct task name or IDs.",
    4040: "Subtask features require an RTM Pro account.",
    4050: "Call list_tasks to verify the parent task ID exists.",
    4060: "RTM allows max 3 nesting levels. Promote an intermediate task first.",
    4070: "A repeating task cannot be a parent or child of another repeating task.",
    4080: "Due date must be after start date (or vice versa). Check both dates.",
    4090: "A task cannot be its own parent. Use a different parent_task_id.",
}


def raise_for_error(code: int, message: str) -> None:
    """Raise appropriate exception based on RTM error code."""
    error_class = ERROR_CODE_MAP.get(code, RTMError)
    guidance = ERROR_GUIDANCE.get(code)
    full_message = f"{message} — {guidance}" if guidance else message
    raise error_class(full_message, code)
