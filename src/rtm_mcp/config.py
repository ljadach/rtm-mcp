"""RTM MCP Configuration management."""

import json
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RTMConfig(BaseSettings):
    """RTM API configuration.

    Loads from:
    1. Environment variables (RTM_API_KEY, RTM_SHARED_SECRET, RTM_AUTH_TOKEN)
    2. Config file (~/.config/rtm-mcp/config.json)
    3. Legacy config file (~/.config/rtm/config.json)
    """

    model_config = SettingsConfigDict(
        env_prefix="RTM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str = Field(default="", description="RTM API key")
    shared_secret: str = Field(default="", description="RTM shared secret")
    auth_token: str = Field(default="", alias="token", description="RTM auth token")

    @classmethod
    def load(cls) -> "RTMConfig":
        """Load config from environment and/or config files."""
        # Try loading from environment first
        config = cls()

        # If not fully configured, try config files
        if not config.is_configured():
            config = cls._load_from_file(config)

        return config

    @classmethod
    def _load_from_file(cls, base_config: "RTMConfig") -> "RTMConfig":
        """Load config from JSON file."""
        config_paths = [
            Path.home() / ".config" / "rtm-mcp" / "config.json",
            Path.home() / ".config" / "rtm" / "config.json",  # Legacy location
        ]

        for config_path in config_paths:
            if config_path.exists():
                try:
                    data = json.loads(config_path.read_text())
                    return cls(
                        api_key=data.get("api_key", base_config.api_key),
                        shared_secret=data.get("shared_secret", base_config.shared_secret),
                        token=data.get("token", base_config.auth_token),
                    )
                except (json.JSONDecodeError, KeyError):
                    continue

        return base_config

    def is_configured(self) -> bool:
        """Check if all required settings are present."""
        return bool(self.api_key and self.shared_secret and self.auth_token)

    def save(self, path: Path | None = None) -> None:
        """Save config to file."""
        if path is None:
            path = Path.home() / ".config" / "rtm-mcp" / "config.json"

        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "api_key": self.api_key,
            "shared_secret": self.shared_secret,
            "token": self.auth_token,
        }

        path.write_text(json.dumps(data, indent=2))


# RTM API endpoints
RTM_API_URL = "https://api.rememberthemilk.com/services/rest/"
RTM_AUTH_URL = "https://www.rememberthemilk.com/services/auth/"
