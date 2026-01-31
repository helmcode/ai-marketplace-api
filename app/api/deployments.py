from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.models.deployment import Deployment
from app.models.agent_catalog import AgentCatalog
from app.schemas.deployment import (
    DeploymentCreate,
    DeploymentResponse,
    DeploymentListResponse
)
from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError, BadRequestError, ForbiddenError
from app.services.provisioning import provision_deployment, delete_deployment

router = APIRouter(prefix="/deployments", tags=["deployments"])


def deployment_to_response(deployment: Deployment) -> dict:
    """Convert deployment model to response dict with agent info."""
    return {
        "id": deployment.id,
        "agent_id": deployment.agent_id,
        "agent_name": deployment.agent.name if deployment.agent else None,
        "agent_slug": deployment.agent.slug if deployment.agent else None,
        "droplet_id": deployment.droplet_id,
        "ip_address": deployment.ip_address,
        "ssh_user": deployment.ssh_user,
        "status": deployment.status,
        "status_message": deployment.status_message,
        "created_at": deployment.created_at,
        "updated_at": deployment.updated_at
    }


@router.get("", response_model=List[DeploymentListResponse])
async def list_deployments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List current user's deployments."""
    deployments = db.query(Deployment).filter(
        Deployment.user_id == current_user.id,
        Deployment.status != "deleted"
    ).order_by(Deployment.created_at.desc()).all()

    return [
        {
            "id": d.id,
            "agent_name": d.agent.name if d.agent else None,
            "agent_slug": d.agent.slug if d.agent else None,
            "ip_address": d.ip_address,
            "status": d.status,
            "created_at": d.created_at
        }
        for d in deployments
    ]


@router.post("", response_model=DeploymentResponse)
async def create_deployment(
    data: DeploymentCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new deployment."""
    if not current_user.ssh_public_key:
        raise BadRequestError(
            "SSH public key required. Please update your profile with an SSH key first."
        )

    agent = db.query(AgentCatalog).filter(
        AgentCatalog.slug == data.agent_slug,
        AgentCatalog.is_active == 1
    ).first()

    if not agent:
        raise NotFoundError(f"Agent '{data.agent_slug}' not found")

    if not agent.snapshot_id:
        raise BadRequestError("Agent is not ready for deployment")

    deployment = Deployment(
        user_id=current_user.id,
        agent_id=agent.id,
        status="pending"
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)

    async def provision_task():
        try:
            await provision_deployment(
                db=db,
                deployment=deployment,
                agent=agent,
                config=data.config,
                ssh_public_key=current_user.ssh_public_key
            )
        except Exception as e:
            deployment.status = "failed"
            deployment.status_message = str(e)
            db.commit()

    background_tasks.add_task(provision_task)

    return deployment_to_response(deployment)


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get deployment details."""
    deployment = db.query(Deployment).filter(
        Deployment.id == deployment_id
    ).first()

    if not deployment:
        raise NotFoundError("Deployment not found")

    if deployment.user_id != current_user.id:
        raise ForbiddenError("Access denied")

    return deployment_to_response(deployment)


@router.delete("/{deployment_id}")
async def remove_deployment(
    deployment_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a deployment."""
    deployment = db.query(Deployment).filter(
        Deployment.id == deployment_id
    ).first()

    if not deployment:
        raise NotFoundError("Deployment not found")

    if deployment.user_id != current_user.id:
        raise ForbiddenError("Access denied")

    if deployment.status == "deleted":
        raise BadRequestError("Deployment already deleted")

    async def delete_task():
        try:
            await delete_deployment(db, deployment)
        except Exception as e:
            deployment.status_message = f"Delete failed: {str(e)}"
            db.commit()

    background_tasks.add_task(delete_task)

    return {"message": "Deployment deletion initiated"}
