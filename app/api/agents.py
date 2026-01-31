from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.agent_catalog import AgentCatalog
from app.schemas.agent import AgentResponse, AgentListResponse
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=List[AgentListResponse])
async def list_agents(db: Session = Depends(get_db)):
    """List all available agents in the marketplace."""
    agents = db.query(AgentCatalog).filter(AgentCatalog.is_active == 1).all()
    return agents


@router.get("/{slug}", response_model=AgentResponse)
async def get_agent(slug: str, db: Session = Depends(get_db)):
    """Get agent details by slug."""
    agent = db.query(AgentCatalog).filter(
        AgentCatalog.slug == slug,
        AgentCatalog.is_active == 1
    ).first()

    if not agent:
        raise NotFoundError(f"Agent '{slug}' not found")

    return agent
