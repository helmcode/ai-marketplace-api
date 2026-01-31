from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional, Any


class AgentResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    long_description: Optional[str] = None
    icon_url: Optional[str] = None
    config_schema: Optional[dict[str, Any]] = None
    base_price: int
    created_at: datetime

    class Config:
        from_attributes = True


class AgentListResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    base_price: int

    class Config:
        from_attributes = True
