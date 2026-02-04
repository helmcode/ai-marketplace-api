from fastapi import Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.core.security import verify_jwt
from app.core.exceptions import UnauthorizedError, NotFoundError

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token."""
    token = credentials.credentials
    payload = await verify_jwt(token)

    auth0_id = payload.get("sub")
    if not auth0_id:
        raise UnauthorizedError("Invalid token payload")

    user = db.query(User).filter(User.auth0_id == auth0_id).first()

    # Get real email from token (Auth0 provides it in different places)
    real_email = payload.get("email") or payload.get(
        "https://ai-marketplace.com/email"
    )

    if not user:
        email = real_email or f"{auth0_id}@auth0.local"
        user = User(auth0_id=auth0_id, email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif real_email and user.email.endswith("@auth0.local"):
        # Update email if we now have a real one and current is placeholder
        user.email = real_email
        db.commit()
        db.refresh(user)

    return user


async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, None otherwise."""
    if not authorization or not authorization.startswith("Bearer "):
        return None

    try:
        token = authorization.split(" ")[1]
        payload = await verify_jwt(token)
        auth0_id = payload.get("sub")

        if auth0_id:
            return db.query(User).filter(User.auth0_id == auth0_id).first()
    except Exception:
        pass

    return None
