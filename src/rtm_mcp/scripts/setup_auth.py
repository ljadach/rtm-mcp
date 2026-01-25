#!/usr/bin/env python3
"""Interactive setup script for RTM MCP authentication."""

import asyncio
import sys
import webbrowser
from pathlib import Path


def print_header() -> None:
    """Print setup header."""
    print()
    print("=" * 60)
    print("  RTM MCP Server - Authentication Setup")
    print("=" * 60)
    print()


def print_step(step: int, total: int, message: str) -> None:
    """Print step indicator."""
    print(f"\n[{step}/{total}] {message}")
    print("-" * 40)


async def run_setup() -> None:
    """Run the interactive setup process."""
    from rtm_mcp.client import RTMAuthFlow
    from rtm_mcp.config import RTMConfig

    print_header()

    # Check for existing config
    config = RTMConfig.load()
    if config.is_configured():
        print("Existing configuration found.")
        response = input("Do you want to reconfigure? [y/N]: ").strip().lower()
        if response != "y":
            print("Setup cancelled.")
            return

    # Step 1: Get API credentials
    print_step(1, 4, "API Credentials")
    print("Get your API key and shared secret from:")
    print("  https://www.rememberthemilk.com/services/api/keys.rtm")
    print()

    api_key = input("API Key: ").strip()
    if not api_key:
        print("Error: API key is required.")
        sys.exit(1)

    shared_secret = input("Shared Secret: ").strip()
    if not shared_secret:
        print("Error: Shared secret is required.")
        sys.exit(1)

    # Step 2: Start auth flow
    print_step(2, 4, "Authorization")

    auth_flow = RTMAuthFlow(api_key, shared_secret)

    print("Getting authorization URL...")
    try:
        frob = await auth_flow.get_frob()
    except Exception as e:
        print(f"Error getting frob: {e}")
        print("Please check your API key and shared secret.")
        sys.exit(1)

    auth_url = auth_flow.get_auth_url(frob, perms="delete")

    print()
    print("Please authorize RTM MCP in your browser.")
    print()
    print("Authorization URL:")
    print(f"  {auth_url}")
    print()

    # Try to open browser
    try:
        webbrowser.open(auth_url)
        print("(Browser should open automatically)")
    except Exception:
        print("(Please copy the URL and open it in your browser)")

    # Step 3: Wait for authorization
    print_step(3, 4, "Waiting for Authorization")
    print("After authorizing in your browser, press Enter to continue...")
    input()

    # Step 4: Get token
    print_step(4, 4, "Getting Auth Token")

    try:
        token, user_info = await auth_flow.get_token(frob)
    except Exception as e:
        print(f"Error getting token: {e}")
        print()
        print("Common issues:")
        print("  - Did you authorize the app in your browser?")
        print("  - Did you wait for the authorization to complete?")
        print()
        print("Please try again.")
        sys.exit(1)

    # Save config
    new_config = RTMConfig(
        api_key=api_key,
        shared_secret=shared_secret,
        token=token,
    )

    config_path = Path.home() / ".config" / "rtm-mcp" / "config.json"
    new_config.save(config_path)

    print()
    print("=" * 60)
    print("  Setup Complete!")
    print("=" * 60)
    print()
    print(f"Authenticated as: {user_info.get('fullname', user_info.get('username', 'Unknown'))}")
    print(f"Config saved to: {config_path}")
    print()
    print("You can now use RTM MCP!")
    print()
    print("Quick test:")
    print("  rtm-mcp  (starts the server)")
    print()
    print("Claude Desktop config (~/.config/claude/claude_desktop_config.json):")
    print("""
{
  "mcpServers": {
    "rtm": {
      "command": "uvx",
      "args": ["rtm-mcp"]
    }
  }
}
""")


def main() -> None:
    """Main entry point."""
    try:
        asyncio.run(run_setup())
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(1)


if __name__ == "__main__":
    main()
