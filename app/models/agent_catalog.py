from sqlalchemy import Column, String, Text, Integer, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class AgentCatalog(Base):
    __tablename__ = "agent_catalog"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text)
    long_description = Column(Text)
    icon_url = Column(String(500))
    config_schema = Column(JSON)
    snapshot_id = Column(String(100))
    droplet_size = Column(String(50), default="s-1vcpu-2gb")
    droplet_region = Column(String(20), default="nyc1")
    base_price = Column(Integer, default=0)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    deployments = relationship("Deployment", back_populates="agent")

    def __repr__(self):
        return f"<AgentCatalog {self.name}>"
