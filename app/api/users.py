from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from app.api.deps import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user's profile."""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile."""
    if update_data.ssh_public_key is not None:
        ssh_key = update_data.ssh_public_key.strip()
        if ssh_key and not (
            ssh_key.startswith("ssh-rsa") or
            ssh_key.startswith("ssh-ed25519") or
            ssh_key.startswith("ecdsa-")
        ):
            from app.core.exceptions import BadRequestError
            raise BadRequestError("Invalid SSH public key format")

        current_user.ssh_public_key = ssh_key if ssh_key else None

    db.commit()
    db.refresh(current_user)

    return current_user
