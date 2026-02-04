import asyncio
from typing import Optional, Callable
from uuid import UUID
from datetime import datetime
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from sqlalchemy.orm import Session

from app.models import Box, BoxAgent, BoxStatus, BoxAgentStatus, BOX_TIER_SPECS, BoxTier, AgentCatalog
from app.services.digitalocean import get_digitalocean_service
from app.services.ssh import SSHService
from app.core.security import encrypt_value, decrypt_value
from app.core.exceptions import BadRequestError, NotFoundError


class BoxProvisioningService:
    """Service for provisioning and managing boxes (VPS instances)."""

    # Ubuntu 24.04 LTS image slug
    UBUNTU_IMAGE = "ubuntu-24-04-x64"

    def __init__(self, db: Session):
        self.db = db
        self.do_service = get_digitalocean_service()

    def _generate_ssh_keypair(self) -> tuple[str, str]:
        """Generate a new RSA SSH keypair for backend access."""
        key = rsa.generate_private_key(
            backend=default_backend(),
            public_exponent=65537,
            key_size=4096
        )

        private_key = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')

        public_key = key.public_key().public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        ).decode('utf-8')

        return private_key, public_key

    async def provision_box(
        self,
        box: Box,
        user_ssh_public_key: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Box:
        """
        Provision a new box with clean Ubuntu.

        Steps:
        1. Generate system SSH keypair for backend access
        2. Add SSH keys to Digital Ocean
        3. Create droplet with clean Ubuntu image
        4. Wait for droplet to become active
        5. Store system private key (encrypted)
        """

        def update_status(message: str):
            box.status_message = message
            box.updated_at = datetime.utcnow()
            self.db.commit()
            if progress_callback:
                progress_callback(message)

        try:
            box.status = BoxStatus.PROVISIONING.value
            update_status("Generating SSH keys...")

            # Generate system SSH keypair
            private_key, public_key = self._generate_ssh_keypair()

            # Add system SSH key to cloud provider
            update_status("Configuring secure access...")
            key_name = f"box-{box.id}-system"
            key_result = await self.do_service.add_ssh_key(key_name, public_key)
            system_key_id = key_result["ssh_key"]["id"]

            # Collect SSH keys for droplet
            ssh_key_ids = [system_key_id]

            # Add user's SSH key if provided
            if user_ssh_public_key:
                update_status("Adding user SSH key...")
                user_key_result = await self.do_service.add_ssh_key(
                    f"user-{box.user_id}",
                    user_ssh_public_key
                )
                ssh_key_ids.append(user_key_result["ssh_key"]["id"])

            # Get tier specifications
            tier_specs = BOX_TIER_SPECS.get(BoxTier(box.tier), BOX_TIER_SPECS[BoxTier.BASIC])

            # Create droplet
            update_status(f"Creating {tier_specs['display_name']} Box...")
            droplet_name = f"box-{box.id}"
            droplet_result = await self.do_service.create_droplet(
                name=droplet_name,
                snapshot_id=self.UBUNTU_IMAGE,
                ssh_key_ids=ssh_key_ids,
                size=tier_specs["do_size"],
                region=box.region,
                tags=["ai-marketplace", "box", box.tier]
            )

            droplet_id = str(droplet_result["droplet"]["id"])
            box.droplet_id = droplet_id
            self.db.commit()

            # Wait for droplet to be active
            update_status("Waiting for Box to become active...")
            ip_address = await self.do_service.wait_for_droplet_active(
                droplet_id,
                timeout=300,
                poll_interval=10
            )

            # Store results
            box.ip_address = ip_address
            box.system_ssh_key_id = str(system_key_id)
            box.system_private_key = encrypt_value(private_key)
            box.status = BoxStatus.RUNNING.value
            # Mark user SSH as synced if key was provided during creation
            if user_ssh_public_key:
                box.user_ssh_synced = '1'
            update_status("Box is ready!")

            self.db.commit()
            return box

        except Exception as e:
            box.status = BoxStatus.FAILED.value
            box.status_message = f"Provisioning failed: {str(e)}"
            self.db.commit()
            raise

    async def delete_box(self, box: Box) -> None:
        """Delete a box and its droplet."""
        if box.droplet_id:
            try:
                await self.do_service.delete_droplet(box.droplet_id)
            except Exception:
                pass

        box.status = BoxStatus.DELETED.value
        box.status_message = "Box deleted"
        box.updated_at = datetime.utcnow()
        self.db.commit()

    def _get_ssh_service(self, box: Box) -> SSHService:
        """Get SSH service for a box using the system private key."""
        if not box.system_private_key:
            raise BadRequestError("Box does not have system SSH key configured")

        private_key = decrypt_value(box.system_private_key)
        return SSHService(
            host=box.ip_address,
            username="root",
            private_key=private_key
        )

    async def install_agent(
        self,
        box_agent: BoxAgent,
        agent: AgentCatalog,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> BoxAgent:
        """
        Install an agent inside a box.

        Steps:
        1. Connect to box via SSH
        2. Run agent's install command
        3. Stream output to callback
        4. Update status
        """
        box = box_agent.box

        if box.status != BoxStatus.RUNNING.value:
            raise BadRequestError("Box is not running")

        def update_status(message: str, log_append: str = None):
            box_agent.status_message = message
            if log_append:
                if box_agent.install_log:
                    box_agent.install_log += log_append
                else:
                    box_agent.install_log = log_append
            box_agent.updated_at = datetime.utcnow()
            self.db.commit()
            if progress_callback:
                progress_callback(log_append or message)

        try:
            box_agent.status = BoxAgentStatus.INSTALLING.value
            update_status("Connecting to box...")

            ssh = self._get_ssh_service(box)

            # Get install command
            install_command = agent.install_command
            if not install_command and agent.install_script_url:
                install_command = f"curl -fsSL {agent.install_script_url} | bash"

            if not install_command:
                raise BadRequestError(f"Agent {agent.name} does not have an install command")

            update_status(f"Running: {install_command}\n", f"$ {install_command}\n")

            # Execute install command
            stdout, stderr, exit_code = await ssh.execute(install_command, timeout=600)

            # Log output
            if stdout:
                update_status("", stdout)
            if stderr:
                update_status("", f"\nSTDERR:\n{stderr}")

            if exit_code != 0:
                box_agent.status = BoxAgentStatus.FAILED.value
                update_status(f"Installation failed with exit code {exit_code}")
            else:
                box_agent.status = BoxAgentStatus.RUNNING.value
                update_status("Installation completed successfully!")

            self.db.commit()
            return box_agent

        except Exception as e:
            box_agent.status = BoxAgentStatus.FAILED.value
            box_agent.status_message = f"Installation failed: {str(e)}"
            self.db.commit()
            raise

    async def execute_command(
        self,
        box: Box,
        command: str,
        timeout: int = 60
    ) -> tuple[str, str, int]:
        """Execute a command on a box."""
        if box.status != BoxStatus.RUNNING.value:
            raise BadRequestError("Box is not running")

        ssh = self._get_ssh_service(box)
        return await ssh.execute(command, timeout=timeout)

    async def get_agent_tui_command(self, box_agent: BoxAgent, agent: AgentCatalog) -> str:
        """Get the TUI command for an agent."""
        if agent.tui_command:
            return agent.tui_command
        return "openclaw tui"

    async def sync_user_ssh_key(self, box: Box, user_ssh_public_key: str) -> Box:
        """
        Sync user's SSH public key to a running box.

        This adds the user's key to ~/.ssh/authorized_keys on the box,
        allowing them to SSH directly.
        """
        if box.status != BoxStatus.RUNNING.value:
            raise BadRequestError("Box is not running")

        if not box.ip_address:
            raise BadRequestError("Box does not have an IP address")

        if not user_ssh_public_key:
            raise BadRequestError("No SSH public key provided")

        ssh = self._get_ssh_service(box)

        # Add user's SSH key to authorized_keys
        # Using a heredoc to safely handle the key content
        add_key_command = f'''
mkdir -p ~/.ssh && chmod 700 ~/.ssh
grep -qxF "{user_ssh_public_key}" ~/.ssh/authorized_keys 2>/dev/null || echo "{user_ssh_public_key}" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
'''
        stdout, stderr, exit_code = await ssh.execute(add_key_command, timeout=30)

        if exit_code != 0:
            raise BadRequestError(f"Failed to add SSH key: {stderr}")

        # Mark as synced
        box.user_ssh_synced = '1'
        box.updated_at = datetime.utcnow()
        self.db.commit()

        return box


def get_box_provisioning_service(db: Session) -> BoxProvisioningService:
    """Get box provisioning service instance."""
    return BoxProvisioningService(db)
