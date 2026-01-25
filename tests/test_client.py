"""Tests for RTM client."""

import httpx
import pytest
import respx

from rtm_mcp.client import RTMClient
from rtm_mcp.config import RTM_API_URL, RTMConfig
from rtm_mcp.exceptions import RTMAuthError, RTMError


@pytest.fixture
def client(mock_config: RTMConfig) -> RTMClient:
    """Create a test client."""
    return RTMClient(mock_config)


class TestRTMClient:
    """Test RTMClient functionality."""

    def test_sign_request(self, client: RTMClient) -> None:
        """Test MD5 signing."""
        params = {"api_key": "test", "method": "rtm.test.echo"}
        signature = client._sign(params)

        # Verify signature format
        assert len(signature) == 32
        assert all(c in "0123456789abcdef" for c in signature)

        # Verify signature is reproducible
        assert client._sign(params) == signature

    def test_sign_order_independent(self, client: RTMClient) -> None:
        """Test that signing is order-independent."""
        params1 = {"a": "1", "b": "2", "c": "3"}
        params2 = {"c": "3", "a": "1", "b": "2"}

        assert client._sign(params1) == client._sign(params2)

    @respx.mock
    @pytest.mark.asyncio
    async def test_call_success(self, client: RTMClient) -> None:
        """Test successful API call."""
        respx.get(RTM_API_URL).mock(
            return_value=httpx.Response(
                200,
                json={"rsp": {"stat": "ok", "test": "hello"}},
            )
        )

        result = await client.call("rtm.test.echo", test="hello")

        assert result["stat"] == "ok"
        assert result["test"] == "hello"

        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_call_auth_error(self, client: RTMClient) -> None:
        """Test auth error handling."""
        respx.get(RTM_API_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "rsp": {
                        "stat": "fail",
                        "err": {"code": "98", "msg": "Login failed"},
                    }
                },
            )
        )

        with pytest.raises(RTMAuthError):
            await client.call("rtm.test.echo")

        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_call_generic_error(self, client: RTMClient) -> None:
        """Test generic error handling."""
        respx.get(RTM_API_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "rsp": {
                        "stat": "fail",
                        "err": {"code": "999", "msg": "Unknown error"},
                    }
                },
            )
        )

        with pytest.raises(RTMError) as exc_info:
            await client.call("rtm.test.echo")

        assert "Unknown error" in str(exc_info.value)

        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_timeline(self, client: RTMClient) -> None:
        """Test timeline creation."""
        respx.get(RTM_API_URL).mock(
            return_value=httpx.Response(
                200,
                json={"rsp": {"stat": "ok", "timeline": "12345"}},
            )
        )

        timeline = await client.get_timeline()
        assert timeline == "12345"

        # Should cache and return same timeline
        timeline2 = await client.get_timeline()
        assert timeline2 == "12345"

        await client.close()


class TestRTMConfig:
    """Test configuration loading."""

    def test_is_configured(self) -> None:
        """Test configuration validation."""
        # Not configured
        config = RTMConfig()
        assert not config.is_configured()

        # Partially configured
        config = RTMConfig(api_key="key")
        assert not config.is_configured()

        # Fully configured (note: auth_token uses alias "token")
        config = RTMConfig(
            api_key="key",
            shared_secret="secret",
            token="token",
        )
        assert config.is_configured()
