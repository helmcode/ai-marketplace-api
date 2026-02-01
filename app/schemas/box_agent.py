from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Optional, Any
from enum import Enum


class BoxAgentStatusEnum(str, Enum):
    """Agent installation and runtime status."""
    PENDING = "pending"
    INSTALLING = "installing"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class BoxAgentCreate(BaseModel):
    """Request to install an agent in a box."""
    agent_slug: str = Field(..., description="Slug of the agent from catalog")
    instance_name: str = Field(..., min_length=1, max_length=100, description="Name for this agent instance")
    config: Optional[dict[str, Any]] = Field(default=None, description="Agent configuration")


class BoxAgentResponse(BaseModel):
    """Full agent instance details."""
    id: UUID
    box_id: UUID
    agent_id: UUID
    instance_name: str
    install_script_url: Optional[str] = None
    status: str
    status_message: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    # Agent catalog info (joined)
    agent_name: Optional[str] = None
    agent_slug: Optional[str] = None
    agent_icon_url: Optional[str] = None
    tui_command: Optional[str] = None

    class Config:
        from_attributes = True


class BoxAgentListResponse(BaseModel):
    """Lightweight agent instance info for list display."""
    id: UUID
    box_id: UUID
    instance_name: str
    status: str
    agent_name: Optional[str] = None
    agent_slug: Optional[str] = None
    agent_icon_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BoxAgentUpdate(BaseModel):
    """Request to update an agent instance."""
    instance_name: Optional[str] = Field(None, min_length=1, max_length=100)
    config: Optional[dict[str, Any]] = None


class BoxAgentInstallLog(BaseModel):
    """Installation log response."""
    id: UUID
    status: str
    install_log: Optional[str] = None
    status_message: Optional[str] = None

    class Config:
        from_attributes = True
