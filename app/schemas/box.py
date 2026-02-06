from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Optional
from enum import Enum


class BoxTierEnum(str, Enum):
    """Box tier options."""
    BASIC = "basic"
    MEDIUM = "medium"
    PRO = "pro"


class BoxStatusEnum(str, Enum):
    """Box lifecycle status."""
    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    DELETED = "deleted"


class TierSpec(BaseModel):
    """Specification for a box tier."""
    tier: BoxTierEnum
    display_name: str
    description: str
    cpu: int
    ram_gb: int
    price_cents: int

    class Config:
        from_attributes = True


class TierListResponse(BaseModel):
    """Response containing all available tiers."""
    tiers: list[TierSpec]


class BoxCreate(BaseModel):
    """Request to create a new box."""
    name: str = Field(..., min_length=1, max_length=100, description="User-given name for the box")
    tier: BoxTierEnum = Field(default=BoxTierEnum.BASIC, description="Box tier (basic/medium/pro)")
    region: str = Field(default="nyc1", description="Digital Ocean region")


class BoxResponse(BaseModel):
    """Full box details response."""
    id: UUID
    user_id: UUID
    name: str
    tier: str
    droplet_id: Optional[str] = None
    ip_address: Optional[str] = None
    region: str
    status: str
    status_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Tier specifications (computed)
    tier_display_name: Optional[str] = None
    tier_cpu: Optional[int] = None
    tier_ram_gb: Optional[int] = None
    tier_price_cents: Optional[int] = None

    # User SSH access
    user_ssh_synced: bool = False

    # Subscription info
    subscription_status: Optional[str] = None
    subscription_cancel_at: Optional[datetime] = None
    subscription_grace_period_end: Optional[datetime] = None

    class Config:
        from_attributes = True


class BoxListResponse(BaseModel):
    """Lightweight box info for list display."""
    id: UUID
    name: str
    tier: str
    ip_address: Optional[str] = None
    region: str
    status: str
    agent_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class BoxUpdate(BaseModel):
    """Request to update a box (limited fields)."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
