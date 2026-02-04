from pydantic import BaseModel, EmailStr
from datetime import datetime
from uuid import UUID
from typing import Optional


class UserCreate(BaseModel):
    auth0_id: str
    email: EmailStr


class UserUpdate(BaseModel):
    ssh_public_key: Optional[str] = None


class UserResponse(BaseModel):
    id: UUID
    email: str  # Changed from EmailStr - Auth0 can return non-email identifiers
    ssh_public_key: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
