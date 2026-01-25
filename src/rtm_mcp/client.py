"""Async RTM API Client."""

import asyncio
import hashlib
from typing import Any

import httpx

from .config import RTM_API_URL, RTMConfig
from .exceptions import RTMError, RTMNetworkError, RTMRateLimitError, raise_for_error


class RTMClient:
    """Async Remember The Milk API client.

    Features:
    - MD5 request signing
    - Timeline management for write operations
    - Rate limiting (1 RPS with burst)
    - Connection pooling via httpx
    """

    def __init__(self, config: RTMConfig):
        self.config = config
        self._timeline: str | None = None
        self._http: httpx.AsyncClient | None = None
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time: float = 0

    async def _get_http(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_keepalive_connections=5),
            )
        return self._http

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http:
            await self._http.aclose()
            self._http = None

    def _sign(self, params: dict[str, str]) -> str:
        """Generate MD5 API signature."""
        sorted_params = sorted(params.items())
        param_string = "".join(f"{k}{v}" for k, v in sorted_params)
        sig_input = self.config.shared_secret + param_string
        return hashlib.md5(sig_input.encode()).hexdigest()

    async def _rate_limit(self) -> None:
        """Enforce rate limiting (1 RPS)."""
        async with self._rate_limit_lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < 1.0:
                await asyncio.sleep(1.0 - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    async def call(
        self,
        method: str,
        *,
        require_timeline: bool = False,
        **params: Any,
    ) -> dict[str, Any]:
        """Make an authenticated RTM API call.

        Args:
            method: RTM API method (e.g., 'rtm.tasks.getList')
            require_timeline: Whether to include a timeline (for write ops)
            **params: Additional parameters

        Returns:
            API response dict (without 'rsp' wrapper)

        Raises:
            RTMError: On API errors
            RTMNetworkError: On connection errors
        """
        await self._rate_limit()

        # Build request params
        request_params: dict[str, str] = {
            "method": method,
            "api_key": self.config.api_key,
            "auth_token": self.config.auth_token,
            "format": "json",
        }

        # Add timeline for write operations
        if require_timeline:
            request_params["timeline"] = await self.get_timeline()

        # Add caller params (converting to string)
        for key, value in params.items():
            if value is not None:
                request_params[key] = str(value)

        # Sign the request
        request_params["api_sig"] = self._sign(request_params)

        try:
            http = await self._get_http()
            response = await http.get(RTM_API_URL, params=request_params)
            response.raise_for_status()

            result = response.json()
            rsp = result.get("rsp", {})

            if rsp.get("stat") != "ok":
                err = rsp.get("err", {})
                code = int(err.get("code", 0))
                msg = err.get("msg", "Unknown error")
                raise_for_error(code, msg)

            return rsp

        except httpx.TimeoutException as e:
            raise RTMNetworkError("Request timed out") from e
        except httpx.ConnectError as e:
            raise RTMNetworkError("Failed to connect to RTM API") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RTMRateLimitError("Rate limit exceeded") from e
            raise RTMNetworkError(f"HTTP error: {e.response.status_code}") from e

    async def get_timeline(self) -> str:
        """Get or create a timeline for write operations.

        Timelines are required for all write operations and can be used
        to undo operations via rtm.transactions.undo.
        """
        if self._timeline is None:
            result = await self.call("rtm.timelines.create")
            self._timeline = str(result["timeline"])
        return self._timeline

    async def test_echo(self) -> dict[str, Any]:
        """Test API connectivity (rtm.test.echo)."""
        return await self.call("rtm.test.echo", test="hello")

    async def check_token(self) -> dict[str, Any]:
        """Check if auth token is valid (rtm.auth.checkToken)."""
        return await self.call("rtm.auth.checkToken")


class RTMAuthFlow:
    """Handle RTM authentication flow (frob → token)."""

    def __init__(self, api_key: str, shared_secret: str):
        self.api_key = api_key
        self.shared_secret = shared_secret

    def _sign(self, params: dict[str, str]) -> str:
        """Generate MD5 signature."""
        sorted_params = sorted(params.items())
        param_string = "".join(f"{k}{v}" for k, v in sorted_params)
        return hashlib.md5((self.shared_secret + param_string).encode()).hexdigest()

    async def get_frob(self) -> str:
        """Get a frob for authentication."""
        params = {
            "method": "rtm.auth.getFrob",
            "api_key": self.api_key,
            "format": "json",
        }
        params["api_sig"] = self._sign(params)

        async with httpx.AsyncClient() as http:
            response = await http.get(RTM_API_URL, params=params)
            response.raise_for_status()
            result = response.json()

            if result["rsp"]["stat"] != "ok":
                err = result["rsp"].get("err", {})
                raise RTMError(err.get("msg", "Failed to get frob"))

            return result["rsp"]["frob"]

    def get_auth_url(self, frob: str, perms: str = "delete") -> str:
        """Generate auth URL for user to visit.

        Args:
            frob: Frob from get_frob()
            perms: Permission level (read, write, delete)

        Returns:
            URL for user to authorize the app
        """
        from .config import RTM_AUTH_URL

        params = {
            "api_key": self.api_key,
            "perms": perms,
            "frob": frob,
        }
        params["api_sig"] = self._sign(params)

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{RTM_AUTH_URL}?{query}"

    async def get_token(self, frob: str) -> tuple[str, dict[str, Any]]:
        """Exchange frob for auth token.

        Args:
            frob: Authorized frob

        Returns:
            Tuple of (token, user_info)
        """
        params = {
            "method": "rtm.auth.getToken",
            "api_key": self.api_key,
            "frob": frob,
            "format": "json",
        }
        params["api_sig"] = self._sign(params)

        async with httpx.AsyncClient() as http:
            response = await http.get(RTM_API_URL, params=params)
            response.raise_for_status()
            result = response.json()

            if result["rsp"]["stat"] != "ok":
                err = result["rsp"].get("err", {})
                raise RTMError(err.get("msg", "Failed to get token"))

            auth = result["rsp"]["auth"]
            return auth["token"], auth.get("user", {})
