"""
Seed script to populate initial data.

Usage:
    python -m scripts.seed
"""
import sys
sys.path.insert(0, '.')

from app.database import SessionLocal
from app.models.agent_catalog import AgentCatalog


OPENCLAW_CONFIG_SCHEMA = {
    "type": "object",
    "required": ["provider", "api_key", "model"],
    "properties": {
        "provider": {
            "type": "string",
            "title": "AI Provider",
            "description": "Select your AI model provider",
            "enum": ["anthropic", "openai", "openrouter"],
            "enumLabels": {
                "anthropic": "Anthropic (Claude)",
                "openai": "OpenAI (GPT)",
                "openrouter": "OpenRouter"
            },
            "default": "anthropic"
        },
        "api_key": {
            "type": "string",
            "title": "API Key",
            "description": "Your provider's API key",
            "format": "password"
        },
        "model": {
            "type": "string",
            "title": "Model",
            "description": "AI model to use",
            "dependsOn": "provider",
            "options": {
                "anthropic": [
                    {"value": "claude-sonnet-4-5", "label": "Claude Sonnet 4.5"},
                    {"value": "claude-opus-4-5", "label": "Claude Opus 4.5"}
                ],
                "openai": [
                    {"value": "gpt-4o", "label": "GPT-4o"},
                    {"value": "gpt-4-turbo", "label": "GPT-4 Turbo"}
                ],
                "openrouter": [
                    {"value": "anthropic/claude-3-opus", "label": "Claude 3 Opus"},
                    {"value": "openai/gpt-4-turbo", "label": "GPT-4 Turbo"},
                    {"value": "meta-llama/llama-3-70b", "label": "Llama 3 70B"}
                ]
            }
        },
        "agent_name": {
            "type": "string",
            "title": "Agent Name",
            "description": "Give your agent a friendly name",
            "default": "Claw",
            "maxLength": 50
        }
    }
}

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


def seed_agents():
    db = SessionLocal()

    try:
        existing = db.query(AgentCatalog).filter(AgentCatalog.slug == "openclaw").first()

        if existing:
            print("OpenClaw agent already exists, updating...")
            existing.name = "OpenClaw"
            existing.description = OPENCLAW_DESCRIPTION
            existing.long_description = OPENCLAW_LONG_DESCRIPTION
            existing.config_schema = OPENCLAW_CONFIG_SCHEMA
            existing.base_price = 2900  # $29.00
            existing.droplet_size = "s-1vcpu-2gb"
            existing.droplet_region = "nyc1"
            existing.is_active = 1
            # New box model fields
            existing.install_script_url = OPENCLAW_INSTALL_SCRIPT_URL
            existing.install_command = OPENCLAW_INSTALL_COMMAND
            existing.tui_command = OPENCLAW_TUI_COMMAND
        else:
            print("Creating OpenClaw agent...")
            agent = AgentCatalog(
                name="OpenClaw",
                slug="openclaw",
                description=OPENCLAW_DESCRIPTION,
                long_description=OPENCLAW_LONG_DESCRIPTION,
                icon_url="/agents/openclaw.svg",
                config_schema=OPENCLAW_CONFIG_SCHEMA,
                snapshot_id=None,  # Legacy field, not used in box model
                droplet_size="s-1vcpu-2gb",
                droplet_region="nyc1",
                base_price=2900,
                is_active=1,
                # New box model fields
                install_script_url=OPENCLAW_INSTALL_SCRIPT_URL,
                install_command=OPENCLAW_INSTALL_COMMAND,
                tui_command=OPENCLAW_TUI_COMMAND
            )
            db.add(agent)

        db.commit()
        print("Seed completed successfully!")

    finally:
        db.close()


if __name__ == "__main__":
    seed_agents()
