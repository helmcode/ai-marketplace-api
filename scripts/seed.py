"""
Seed script to populate initial data.

Usage:
    python -m scripts.seed
"""
import sys
sys.path.insert(0, '.')

from app.database import SessionLocal
from app.models.agent_catalog import AgentCatalog


OPENCLAW_CONFIG_SCHEMA = {}  # User configures via TUI

OPENCLAW_DESCRIPTION = "Autonomous AI agent with multi-channel messaging support."

OPENCLAW_LONG_DESCRIPTION = """
OpenClaw is a powerful autonomous AI agent that can interact through multiple channels
including WhatsApp, Slack, Telegram, and Discord.

## Features

- **Multi-Channel Support**: Connect your agent to various messaging platforms
- **Customizable Personality**: Define your agent's identity, values, and behavior
- **Persistent Memory**: Your agent remembers conversations and context
- **Tool Integration**: Extend capabilities with custom tools and skills
- **Self-Hosted**: Full control over your data and configuration

## Installation

OpenClaw is installed directly into your Box via the one-click installer.
The installation process:
1. Downloads and installs OpenClaw CLI
2. Sets up the default workspace
3. Configures the gateway

## Interacting with OpenClaw

After installation, use the TUI (Terminal UI) to chat with your agent directly
from the web interface. No SSH required!
"""

# OpenClaw installation script URL
OPENCLAW_INSTALL_SCRIPT_URL = "https://openclaw.ai/install.sh"
OPENCLAW_INSTALL_COMMAND = "curl -fsSL https://openclaw.ai/install.sh | bash"
OPENCLAW_TUI_COMMAND = "openclaw tui"

# Claude Code configuration
CLAUDE_CODE_DESCRIPTION = "Anthropic's official AI coding assistant in your terminal."

CLAUDE_CODE_LONG_DESCRIPTION = """
Claude Code is Anthropic's official agentic coding tool that lives in your terminal.

## Features

- **Agentic Coding**: Claude understands your codebase and can make changes across multiple files
- **Terminal Native**: Works directly in your terminal with a beautiful TUI
- **Context Aware**: Understands project structure, dependencies, and conventions
- **Safe by Default**: Asks for confirmation before making changes
- **Multi-Language**: Supports all major programming languages

## Installation

Claude Code is installed via Anthropic's official installer script.
The installation process:
1. Downloads and installs the Claude CLI
2. Sets up authentication
3. Configures your environment

## Getting Started

After installation, you'll be guided through:
1. Authenticating with your Anthropic account
2. Setting up your API key
3. Starting your first coding session

Use the TUI to interact with Claude directly from your Box.
"""

CLAUDE_CODE_INSTALL_SCRIPT_URL = "https://claude.ai/install.sh"
CLAUDE_CODE_INSTALL_COMMAND = "curl -fsSL https://claude.ai/install.sh | bash"
CLAUDE_CODE_TUI_COMMAND = "claude"


def seed_agent(db, slug: str, data: dict):
    """Create or update an agent in the catalog."""
    existing = db.query(AgentCatalog).filter(AgentCatalog.slug == slug).first()

    if existing:
        print(f"{data['name']} agent already exists, updating...")
        for key, value in data.items():
            setattr(existing, key, value)
    else:
        print(f"Creating {data['name']} agent...")
        agent = AgentCatalog(slug=slug, **data)
        db.add(agent)


def seed_agents():
    db = SessionLocal()

    try:
        # Seed OpenClaw
        seed_agent(db, "openclaw", {
            "name": "OpenClaw",
            "description": OPENCLAW_DESCRIPTION,
            "long_description": OPENCLAW_LONG_DESCRIPTION,
            "icon_url": "/agents/openclaw.svg",
            "config_schema": OPENCLAW_CONFIG_SCHEMA,
            "snapshot_id": None,
            "droplet_size": "s-1vcpu-2gb",
            "droplet_region": "nyc1",
            "base_price": 0,  # Free (user configures via TUI)
            "is_active": 1,
            "install_script_url": OPENCLAW_INSTALL_SCRIPT_URL,
            "install_command": OPENCLAW_INSTALL_COMMAND,
            "tui_command": OPENCLAW_TUI_COMMAND,
        })

        # Seed Claude Code
        seed_agent(db, "claude-code", {
            "name": "Claude Code",
            "description": CLAUDE_CODE_DESCRIPTION,
            "long_description": CLAUDE_CODE_LONG_DESCRIPTION,
            "icon_url": "/agents/claude-code.svg",
            "config_schema": {},  # User configures via TUI
            "snapshot_id": None,
            "droplet_size": "s-1vcpu-2gb",
            "droplet_region": "nyc1",
            "base_price": 0,  # Free (user pays Anthropic directly)
            "is_active": 1,
            "install_script_url": CLAUDE_CODE_INSTALL_SCRIPT_URL,
            "install_command": CLAUDE_CODE_INSTALL_COMMAND,
            "tui_command": CLAUDE_CODE_TUI_COMMAND,
        })

        db.commit()
        print("Seed completed successfully!")

    finally:
        db.close()


if __name__ == "__main__":
    seed_agents()
