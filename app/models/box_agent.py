from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.database import Base


class BoxAgentStatus(str, enum.Enum):
    """Agent installation and runtime status."""
    PENDING = "pending"
    INSTALLING = "installing"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class BoxAgent(Base):
    """
    Represents an agent installed inside a Box.
    Multiple agents can be installed in a single box.
    """
    __tablename__ = "box_agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    box_id = Column(UUID(as_uuid=True), ForeignKey("boxes.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # Reference to agent_catalog

    # User-given name for this agent instance
    instance_name = Column(String(100), nullable=False)

    # Installation details
    install_script_url = Column(String(500), nullable=True)
    install_log = Column(Text, nullable=True)

    # Status tracking
    status = Column(String(20), default=BoxAgentStatus.PENDING.value)
    status_message = Column(Text, nullable=True)

    # Agent configuration (JSON blob for flexibility)
    config = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    box = relationship("Box", back_populates="agents")

    def __repr__(self):
        return f"<BoxAgent {self.instance_name} in Box {self.box_id}>"
