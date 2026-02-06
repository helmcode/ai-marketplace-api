from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.database import Base


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    GRACE_PERIOD = "grace_period"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    box_id = Column(UUID(as_uuid=True), ForeignKey("boxes.id"), nullable=True, index=True)

    # Stripe identifiers
    stripe_customer_id = Column(String(255), nullable=False, index=True)
    stripe_subscription_id = Column(String(255), unique=True, nullable=False, index=True)
    stripe_price_id = Column(String(255), nullable=False)

    # Status
    status = Column(String(30), default=SubscriptionStatus.ACTIVE.value)

    # Grace period tracking
    grace_period_end = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="subscriptions")
    box = relationship("Box", backref="subscription", uselist=False)

    def __repr__(self):
        return f"<Subscription {self.stripe_subscription_id} ({self.status})>"
