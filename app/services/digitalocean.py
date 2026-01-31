import httpx
from typing import Optional
import asyncio

from app.config import get_settings
from app.core.exceptions import ServiceUnavailableError, BadRequestError

settings = get_settings()


class DigitalOceanService:
    """Service for interacting with Digital Ocean API."""

    BASE_URL = "https://api.digitalocean.com/v2"

    def __init__(self):
        self.token = settings.digitalocean_token
        if not self.token:
            raise ValueError("DIGITALOCEAN_TOKEN not configured")

    def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )

    async def create_droplet(
        self,
        name: str,
        snapshot_id: str,
        ssh_key_ids: list[int],
        size: str = "s-1vcpu-2gb",
        region: str = "nyc1",
        tags: Optional[list[str]] = None
    ) -> dict:
        """Create a new droplet from a snapshot."""
        async with self._get_client() as client:
            response = await client.post(
                "/droplets",
                json={
                    "name": name,
                    "region": region,
                    "size": size,
                    "image": snapshot_id,
                    "ssh_keys": ssh_key_ids,
                    "monitoring": True,
                    "tags": tags or ["ai-marketplace"]
                }
            )

            if response.status_code == 202:
                return response.json()

            raise BadRequestError(f"Failed to create droplet: {response.text}")

    async def get_droplet(self, droplet_id: str) -> dict:
        """Get droplet details."""
        async with self._get_client() as client:
            response = await client.get(f"/droplets/{droplet_id}")

            if response.status_code == 200:
                return response.json()

            raise BadRequestError(f"Failed to get droplet: {response.text}")

    async def delete_droplet(self, droplet_id: str) -> bool:
        """Delete a droplet."""
        async with self._get_client() as client:
            response = await client.delete(f"/droplets/{droplet_id}")
            return response.status_code == 204

    async def wait_for_droplet_active(
        self,
        droplet_id: str,
        timeout: int = 300,
        poll_interval: int = 10
    ) -> str:
        """Wait for droplet to become active and return its IP address."""
        elapsed = 0

        while elapsed < timeout:
            data = await self.get_droplet(droplet_id)
            droplet = data.get("droplet", {})

            if droplet.get("status") == "active":
                networks = droplet.get("networks", {})
                v4_networks = networks.get("v4", [])

                for network in v4_networks:
                    if network.get("type") == "public":
                        return network.get("ip_address")

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise ServiceUnavailableError("Droplet did not become active in time")

    async def add_ssh_key(self, name: str, public_key: str) -> dict:
        """Add an SSH key to the account."""
        async with self._get_client() as client:
            response = await client.post(
                "/account/keys",
                json={
                    "name": name,
                    "public_key": public_key.strip()
                }
            )

            if response.status_code == 201:
                return response.json()

            if response.status_code == 422:
                existing = await self.get_ssh_key_by_fingerprint(public_key)
                if existing:
                    return {"ssh_key": existing}

            raise BadRequestError(f"Failed to add SSH key: {response.text}")

    async def get_ssh_key_by_fingerprint(self, public_key: str) -> Optional[dict]:
        """Find an SSH key by its public key content."""
        async with self._get_client() as client:
            response = await client.get("/account/keys")

            if response.status_code == 200:
                keys = response.json().get("ssh_keys", [])
                for key in keys:
                    if key.get("public_key", "").strip() == public_key.strip():
                        return key

            return None

    async def list_snapshots(self) -> list[dict]:
        """List all snapshots."""
        async with self._get_client() as client:
            response = await client.get("/snapshots", params={"resource_type": "droplet"})

            if response.status_code == 200:
                return response.json().get("snapshots", [])

            return []


def get_digitalocean_service() -> DigitalOceanService:
    """Get Digital Ocean service instance."""
    return DigitalOceanService()
