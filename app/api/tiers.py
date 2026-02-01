from fastapi import APIRouter
from typing import List

from app.models.box import BOX_TIER_SPECS, BoxTier
from app.schemas.box import TierSpec, TierListResponse

router = APIRouter(prefix="/tiers", tags=["tiers"])


@router.get("", response_model=TierListResponse)
async def list_tiers():
    """List all available box tiers with specifications."""
    tiers = [
        TierSpec(
            tier=tier,
            display_name=specs["display_name"],
            description=specs["description"],
            cpu=specs["cpu"],
            ram_gb=specs["ram_gb"],
            price_cents=specs["price_cents"]
        )
        for tier, specs in BOX_TIER_SPECS.items()
    ]
    return TierListResponse(tiers=tiers)
