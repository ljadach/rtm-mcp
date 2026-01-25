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
}


def raise_for_error(code: int, message: str) -> None:
    """Raise appropriate exception based on RTM error code."""
    error_class = ERROR_CODE_MAP.get(code, RTMError)
    raise error_class(message, code)
