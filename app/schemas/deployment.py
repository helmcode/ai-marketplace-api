from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional, Any


class DeploymentConfigItem(BaseModel):
    key: str
    value: str
    is_secret: bool = False


class DeploymentCreate(BaseModel):
    agent_slug: str
    config: dict[str, Any]


class DeploymentResponse(BaseModel):
    id: UUID
    agent_id: UUID
    agent_name: Optional[str] = None
    agent_slug: Optional[str] = None
    droplet_id: Optional[str] = None
    ip_address: Optional[str] = None
    ssh_user: str
    status: str
    status_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeploymentListResponse(BaseModel):
    id: UUID
    agent_name: Optional[str] = None
    agent_slug: Optional[str] = None
    ip_address: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
