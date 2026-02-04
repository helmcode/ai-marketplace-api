from sqlalchemy import Column, String, Text, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.database import Base


class BoxTier(str, enum.Enum):
    """Box tier options with different resource allocations."""
    BASIC = "basic"
    MEDIUM = "medium"
    PRO = "pro"


class BoxStatus(str, enum.Enum):
    """Box lifecycle status."""
    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    DELETED = "deleted"


# Tier specifications mapping
BOX_TIER_SPECS = {
    BoxTier.BASIC: {
        "cpu": 1,
        "ram_gb": 2,
        "do_size": "s-1vcpu-2gb",
        "price_cents": 1200,  # $12/mo
        "display_name": "Basic",
        "description": "1 vCPU, 2GB RAM - Good for single agent workloads"
    },
    BoxTier.MEDIUM: {
        "cpu": 2,
        "ram_gb": 4,
        "do_size": "s-2vcpu-4gb",
        "price_cents": 2400,  # $24/mo
        "display_name": "Medium",
        "description": "2 vCPU, 4GB RAM - Good for multiple agents"
    },
    BoxTier.PRO: {
        "cpu": 4,
        "ram_gb": 8,
        "do_size": "s-4vcpu-8gb",
        "price_cents": 4800,  # $48/mo
        "display_name": "PRO",
        "description": "4 vCPU, 8GB RAM - Maximum performance"
    }
}


class Box(Base):
    """
    A Box represents a VPS instance that can host multiple agents.
    Users create boxes with a specific tier, then install agents inside them.
    """
    __tablename__ = "boxes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    tier = Column(String(20), nullable=False, default=BoxTier.BASIC.value)

    # Digital Ocean resources
    droplet_id = Column(String(50), nullable=True)
    ip_address = Column(String(45), nullable=True)
    region = Column(String(20), default="nyc1")

    # Status tracking
    status = Column(String(20), default=BoxStatus.PENDING.value)
    status_message = Column(Text, nullable=True)

    # Backend SSH access (system-managed, not user's key)
    system_ssh_key_id = Column(String(50), nullable=True)
    system_private_key = Column(Text, nullable=True)  # Encrypted

    # User SSH access tracking
    user_ssh_synced = Column(String(1), default='0')  # '0' = not synced, '1' = synced

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    agents = relationship("BoxAgent", back_populates="box", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Box {self.name} ({self.tier})>"

    @property
    def tier_specs(self) -> dict:
        """Get the specifications for this box's tier."""
        return BOX_TIER_SPECS.get(BoxTier(self.tier), BOX_TIER_SPECS[BoxTier.BASIC])

    @property
    def do_size(self) -> str:
        """Get the Digital Ocean size slug for this tier."""
        return self.tier_specs["do_size"]
