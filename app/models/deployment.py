from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_catalog.id"), nullable=False)

    # Digital Ocean
    droplet_id = Column(String(50))
    ip_address = Column(String(45))
    ssh_user = Column(String(50), default="root")

    # Status: pending, provisioning, running, stopped, failed, deleted
    status = Column(String(20), default="pending")
    status_message = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="deployments")
    agent = relationship("AgentCatalog", back_populates="deployments")
    config = relationship("DeploymentConfig", back_populates="deployment", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Deployment {self.id} - {self.status}>"


class DeploymentConfig(Base):
    __tablename__ = "deployment_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deployment_id = Column(UUID(as_uuid=True), ForeignKey("deployments.id"), nullable=False)
    key = Column(String(100), nullable=False)
    value = Column(Text)
    is_secret = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    deployment = relationship("Deployment", back_populates="config")

    def __repr__(self):
        return f"<DeploymentConfig {self.key}>"
