from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class CheckoutSessionCreate(BaseModel):
    """Request to create a Stripe Checkout Session for a new box."""
    box_name: str = Field(..., min_length=1, max_length=100)
    tier: str = Field(..., description="starter | basic | medium | pro")
    region: str = Field(default="nyc1")
    email: Optional[str] = Field(None, description="User's real email from Auth0")


class CheckoutSessionResponse(BaseModel):
    """Response with the Stripe Checkout Session URL."""
    checkout_url: str
    session_id: str


class PortalSessionResponse(BaseModel):
    """Response with the Stripe Customer Portal URL."""
    portal_url: str


class SubscriptionResponse(BaseModel):
    """Subscription info returned in API responses."""
    id: UUID
    status: str
    stripe_subscription_id: str
    stripe_price_id: str
    grace_period_end: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
