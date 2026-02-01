from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db, SessionLocal
from app.models import Box, BoxAgent, BoxAgentStatus, BoxStatus, AgentCatalog, User
from app.schemas.box_agent import (
    BoxAgentCreate,
    BoxAgentResponse,
    BoxAgentListResponse,
    BoxAgentUpdate,
    BoxAgentInstallLog
)
from app.api.deps import get_current_user
from app.services.box_provisioning import get_box_provisioning_service
from app.core.exceptions import NotFoundError, ForbiddenError, BadRequestError

router = APIRouter(prefix="/boxes/{box_id}/agents", tags=["box-agents"])


def _get_user_box(db: Session, box_id: UUID, user: User) -> Box:
    """Get a box and verify ownership."""
    box = db.query(Box).filter(Box.id == box_id).first()

    if not box:
        raise NotFoundError("Box not found")

    if box.user_id != user.id:
        raise ForbiddenError("You don't have access to this box")

    return box


def _enrich_agent_response(box_agent: BoxAgent, agent: AgentCatalog) -> dict:
    """Add agent catalog info to response."""
    return {
        "id": box_agent.id,
        "box_id": box_agent.box_id,
        "agent_id": box_agent.agent_id,
        "instance_name": box_agent.instance_name,
        "install_script_url": box_agent.install_script_url,
        "status": box_agent.status,
        "status_message": box_agent.status_message,
        "config": box_agent.config,
        "created_at": box_agent.created_at,
        "updated_at": box_agent.updated_at,
        "agent_name": agent.name if agent else None,
        "agent_slug": agent.slug if agent else None,
        "agent_icon_url": agent.icon_url if agent else None,
        "tui_command": agent.tui_command if agent else None,
    }


def _enrich_agent_list_response(box_agent: BoxAgent, agent: AgentCatalog) -> dict:
    """Add agent catalog info to list response."""
    return {
        "id": box_agent.id,
        "box_id": box_agent.box_id,
        "instance_name": box_agent.instance_name,
        "status": box_agent.status,
        "agent_name": agent.name if agent else None,
        "agent_slug": agent.slug if agent else None,
        "agent_icon_url": agent.icon_url if agent else None,
        "created_at": box_agent.created_at,
    }


@router.get("", response_model=List[BoxAgentListResponse])
async def list_box_agents(
    box_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all agents installed in a box."""
    box = _get_user_box(db, box_id, current_user)

    agents = db.query(BoxAgent).filter(BoxAgent.box_id == box.id).order_by(BoxAgent.created_at.desc()).all()

    result = []
    for box_agent in agents:
        agent = db.query(AgentCatalog).filter(AgentCatalog.id == box_agent.agent_id).first()
        result.append(_enrich_agent_list_response(box_agent, agent))

    return result


@router.post("", response_model=BoxAgentResponse, status_code=201)
async def install_agent(
    box_id: UUID,
    agent_data: BoxAgentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create an agent record. User will install manually via terminal."""
    box = _get_user_box(db, box_id, current_user)

    if box.status != BoxStatus.RUNNING.value:
        raise BadRequestError("Box must be running to install agents")

    # Find agent in catalog
    agent = db.query(AgentCatalog).filter(
        AgentCatalog.slug == agent_data.agent_slug,
        AgentCatalog.is_active == 1
    ).first()

    if not agent:
        raise NotFoundError(f"Agent '{agent_data.agent_slug}' not found")

    # Create box agent record (user will install via terminal)
    box_agent = BoxAgent(
        box_id=box.id,
        agent_id=agent.id,
        instance_name=agent_data.instance_name,
        install_script_url=agent.install_script_url,
        status=BoxAgentStatus.PENDING.value,
        status_message="Ready for installation - run the install command in the terminal",
        config=agent_data.config
    )
    db.add(box_agent)
    db.commit()
    db.refresh(box_agent)

    return _enrich_agent_response(box_agent, agent)


@router.get("/{agent_id}", response_model=BoxAgentResponse)
async def get_box_agent(
    box_id: UUID,
    agent_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get agent instance details."""
    box = _get_user_box(db, box_id, current_user)

    box_agent = db.query(BoxAgent).filter(
        BoxAgent.id == agent_id,
        BoxAgent.box_id == box.id
    ).first()

    if not box_agent:
        raise NotFoundError("Agent not found in this box")

    agent = db.query(AgentCatalog).filter(AgentCatalog.id == box_agent.agent_id).first()
    return _enrich_agent_response(box_agent, agent)


@router.get("/{agent_id}/log", response_model=BoxAgentInstallLog)
async def get_agent_install_log(
    box_id: UUID,
    agent_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get agent installation log."""
    box = _get_user_box(db, box_id, current_user)

    box_agent = db.query(BoxAgent).filter(
        BoxAgent.id == agent_id,
        BoxAgent.box_id == box.id
    ).first()

    if not box_agent:
        raise NotFoundError("Agent not found in this box")

    return BoxAgentInstallLog(
        id=box_agent.id,
        status=box_agent.status,
        install_log=box_agent.install_log,
        status_message=box_agent.status_message
    )


@router.put("/{agent_id}", response_model=BoxAgentResponse)
async def update_box_agent(
    box_id: UUID,
    agent_id: UUID,
    agent_data: BoxAgentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update agent instance configuration."""
    box = _get_user_box(db, box_id, current_user)

    box_agent = db.query(BoxAgent).filter(
        BoxAgent.id == agent_id,
        BoxAgent.box_id == box.id
    ).first()

    if not box_agent:
        raise NotFoundError("Agent not found in this box")

    if agent_data.instance_name is not None:
        box_agent.instance_name = agent_data.instance_name

    if agent_data.config is not None:
        box_agent.config = agent_data.config

    db.commit()
    db.refresh(box_agent)

    agent = db.query(AgentCatalog).filter(AgentCatalog.id == box_agent.agent_id).first()
    return _enrich_agent_response(box_agent, agent)


@router.delete("/{agent_id}")
async def uninstall_agent(
    box_id: UUID,
    agent_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Uninstall an agent from a box."""
    box = _get_user_box(db, box_id, current_user)

    box_agent = db.query(BoxAgent).filter(
        BoxAgent.id == agent_id,
        BoxAgent.box_id == box.id
    ).first()

    if not box_agent:
        raise NotFoundError("Agent not found in this box")

    db.delete(box_agent)
    db.commit()

    return {"message": "Agent uninstalled successfully"}
