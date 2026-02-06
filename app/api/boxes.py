from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
import asyncio

from app.database import get_db, SessionLocal
from app.models import Box, BoxStatus, BOX_TIER_SPECS, BoxTier, User
from app.schemas.box import BoxCreate, BoxResponse, BoxListResponse, BoxUpdate
from app.api.deps import get_current_user
from app.services.box_provisioning import get_box_provisioning_service
from app.core.exceptions import NotFoundError, ForbiddenError, BadRequestError

router = APIRouter(prefix="/boxes", tags=["boxes"])


def _enrich_box_response(box: Box) -> dict:
    """Add tier specifications to box response."""
    tier_specs = BOX_TIER_SPECS.get(BoxTier(box.tier), BOX_TIER_SPECS[BoxTier.BASIC])
    return {
        "id": box.id,
        "user_id": box.user_id,
        "name": box.name,
        "tier": box.tier,
        "droplet_id": box.droplet_id,
        "ip_address": box.ip_address,
        "region": box.region,
        "status": box.status,
        "status_message": box.status_message,
        "created_at": box.created_at,
        "updated_at": box.updated_at,
        "tier_display_name": tier_specs["display_name"],
        "tier_cpu": tier_specs["cpu"],
        "tier_ram_gb": tier_specs["ram_gb"],
        "tier_price_cents": tier_specs["price_cents"],
        "user_ssh_synced": box.user_ssh_synced == '1',
    }


def _enrich_box_list_response(box: Box) -> dict:
    """Add agent count to box list response."""
    return {
        "id": box.id,
        "name": box.name,
        "tier": box.tier,
        "ip_address": box.ip_address,
        "region": box.region,
        "status": box.status,
        "agent_count": len(box.agents) if box.agents else 0,
        "created_at": box.created_at,
    }


@router.get("", response_model=List[BoxListResponse])
async def list_boxes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all boxes owned by the current user."""
    boxes = db.query(Box).filter(
        Box.user_id == current_user.id,
        Box.status != BoxStatus.DELETED.value
    ).order_by(Box.created_at.desc()).all()

    return [_enrich_box_list_response(box) for box in boxes]


@router.post("", response_model=BoxResponse, status_code=201)
async def create_box(
    box_data: BoxCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new box. Use /api/billing/checkout-session instead."""
    raise BadRequestError("Could not create box. Please try again.")
    # Validate tier
    try:
        BoxTier(box_data.tier.value)
    except ValueError:
        raise BadRequestError(f"Invalid tier: {box_data.tier}")

    # Create box record
    box = Box(
        user_id=current_user.id,
        name=box_data.name,
        tier=box_data.tier.value,
        region=box_data.region,
        status=BoxStatus.PENDING.value,
        status_message="Box creation queued"
    )
    db.add(box)
    db.commit()
    db.refresh(box)

    # Capture values before session closes
    box_id = box.id
    user_ssh_key = current_user.ssh_public_key

    # Start provisioning in background with new session
    async def provision_task():
        db_session = SessionLocal()
        try:
            box_obj = db_session.query(Box).filter(Box.id == box_id).first()
            if box_obj:
                service = get_box_provisioning_service(db_session)
                await service.provision_box(
                    box_obj,
                    user_ssh_public_key=user_ssh_key
                )
        finally:
            db_session.close()

    background_tasks.add_task(provision_task)

    return _enrich_box_response(box)


@router.get("/{box_id}", response_model=BoxResponse)
async def get_box(
    box_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get box details by ID."""
    box = db.query(Box).filter(Box.id == box_id).first()

    if not box:
        raise NotFoundError("Box not found")

    if box.user_id != current_user.id:
        raise ForbiddenError("You don't have access to this box")

    return _enrich_box_response(box)


@router.put("/{box_id}", response_model=BoxResponse)
async def update_box(
    box_id: UUID,
    box_data: BoxUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update box details (name only)."""
    box = db.query(Box).filter(Box.id == box_id).first()

    if not box:
        raise NotFoundError("Box not found")

    if box.user_id != current_user.id:
        raise ForbiddenError("You don't have access to this box")

    if box_data.name is not None:
        box.name = box_data.name
        db.commit()
        db.refresh(box)

    return _enrich_box_response(box)


@router.post("/{box_id}/sync-ssh", response_model=BoxResponse)
async def sync_ssh_key(
    box_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Sync user's SSH public key to the box's authorized_keys."""
    box = db.query(Box).filter(Box.id == box_id).first()

    if not box:
        raise NotFoundError("Box not found")

    if box.user_id != current_user.id:
        raise ForbiddenError("You don't have access to this box")

    if not current_user.ssh_public_key:
        raise BadRequestError("You need to configure your SSH public key first")

    if box.user_ssh_synced == '1':
        raise BadRequestError("SSH key is already synced to this box")

    service = get_box_provisioning_service(db)
    await service.sync_user_ssh_key(box, current_user.ssh_public_key)

    return _enrich_box_response(box)


@router.delete("/{box_id}")
async def delete_box(
    box_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a box and its droplet."""
    box = db.query(Box).filter(Box.id == box_id).first()

    if not box:
        raise NotFoundError("Box not found")

    if box.user_id != current_user.id:
        raise ForbiddenError("You don't have access to this box")

    if box.status == BoxStatus.DELETED.value:
        raise BadRequestError("Box is already deleted")

    # Capture box_id before session closes
    box_id_to_delete = box.id

    # Delete in background with new session
    async def delete_task():
        db_session = SessionLocal()
        try:
            box_obj = db_session.query(Box).filter(Box.id == box_id_to_delete).first()
            if box_obj:
                service = get_box_provisioning_service(db_session)
                await service.delete_box(box_obj)
        finally:
            db_session.close()

    background_tasks.add_task(delete_task)

    return {"message": "Box deletion initiated"}
