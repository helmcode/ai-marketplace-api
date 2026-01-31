import json
import asyncio
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.deployment import Deployment, DeploymentConfig
from app.models.agent_catalog import AgentCatalog
from app.services.digitalocean import get_digitalocean_service
from app.core.security import encrypt_value


async def provision_deployment(
    db: Session,
    deployment: Deployment,
    agent: AgentCatalog,
    config: dict,
    ssh_public_key: str
) -> str:
    """
    Provision a new deployment:
    1. Add user's SSH key to Digital Ocean
    2. Create droplet from snapshot
    3. Wait for droplet to be active
    4. Store configuration
    5. Return IP address
    """
    do_service = get_digitalocean_service()

    deployment.status = "provisioning"
    deployment.status_message = "Adding SSH key..."
    db.commit()

    ssh_key_data = await do_service.add_ssh_key(
        name=f"user-{deployment.user_id}",
        public_key=ssh_public_key
    )
    ssh_key_id = ssh_key_data["ssh_key"]["id"]

    deployment.status_message = "Creating server..."
    db.commit()

    droplet_data = await do_service.create_droplet(
        name=f"agent-{deployment.id}",
        snapshot_id=agent.snapshot_id,
        ssh_key_ids=[ssh_key_id],
        size=agent.droplet_size,
        region=agent.droplet_region,
        tags=["ai-marketplace", f"agent-{agent.slug}"]
    )
    droplet_id = str(droplet_data["droplet"]["id"])
    deployment.droplet_id = droplet_id

    deployment.status_message = "Waiting for server to start..."
    db.commit()

    ip_address = await do_service.wait_for_droplet_active(droplet_id)
    deployment.ip_address = ip_address

    deployment.status_message = "Storing configuration..."
    db.commit()

    for key, value in config.items():
        is_secret = key in ["api_key", "token", "password", "secret"]
        stored_value = encrypt_value(str(value)) if is_secret else str(value)

        config_item = DeploymentConfig(
            deployment_id=deployment.id,
            key=key,
            value=stored_value,
            is_secret=is_secret
        )
        db.add(config_item)

    deployment.status = "running"
    deployment.status_message = None
    db.commit()

    return ip_address


async def delete_deployment(db: Session, deployment: Deployment) -> bool:
    """Delete a deployment and its associated droplet."""
    if deployment.droplet_id:
        do_service = get_digitalocean_service()
        await do_service.delete_droplet(deployment.droplet_id)

    deployment.status = "deleted"
    db.commit()

    return True


def generate_openclaw_config(config: dict) -> dict:
    """Generate openclaw.json content from user config."""
    provider = config.get("provider", "anthropic")
    model = config.get("model", "claude-sonnet-4-5")

    return {
        "auth": {
            "profiles": {
                f"{provider}:api-key": {
                    "provider": provider,
                    "mode": "api-key"
                }
            }
        },
        "agents": {
            "defaults": {
                "model": {
                    "primary": f"{provider}/{model}"
                },
                "workspace": "/root/.openclaw/workspace",
                "maxConcurrent": 4
            }
        },
        "gateway": {
            "port": 54321,
            "mode": "local",
            "bind": "0.0.0.0"
        }
    }


def generate_identity_md(config: dict) -> str:
    """Generate IDENTITY.md content from user config."""
    name = config.get("agent_name", "Claw")

    return f"""# Identity

Name: {name}
Creature: AI Assistant
Vibe: Helpful, efficient, and friendly
Emoji: 🦞
"""
