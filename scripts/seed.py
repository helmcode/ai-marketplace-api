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

## What's Included

- Pre-configured VPS with OpenClaw installed
- SSH access for advanced configuration
- Default workspace files ready to customize
- Gateway running and ready to connect
"""


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
        else:
            print("Creating OpenClaw agent...")
            agent = AgentCatalog(
                name="OpenClaw",
                slug="openclaw",
                description=OPENCLAW_DESCRIPTION,
                long_description=OPENCLAW_LONG_DESCRIPTION,
                icon_url="/agents/openclaw.svg",
                config_schema=OPENCLAW_CONFIG_SCHEMA,
                snapshot_id=None,  # Set this after creating the DO snapshot
                droplet_size="s-1vcpu-2gb",
                droplet_region="nyc1",
                base_price=2900,
                is_active=1
            )
            db.add(agent)

        db.commit()
        print("Seed completed successfully!")

    finally:
        db.close()


if __name__ == "__main__":
    seed_agents()
