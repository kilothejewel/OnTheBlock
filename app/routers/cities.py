from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.cities import visible_cities

router = APIRouter(prefix="/cities", tags=["cities"])


class CityOut(BaseModel):
    slug: str
    name: str
    province: str
    country_code: str
    currency: str
    status: str  # "live" or "beta"


@router.get("", response_model=List[CityOut])
def list_cities() -> List[CityOut]:
    """
    The cities that take new Plans, for the web and mobile pickers: South
    African cities first (live, then beta), then international ones. Hidden
    cities are left out. Open to everyone.
    """
    return [
        CityOut(
            slug=c.slug, name=c.name, province=c.province, country_code=c.country_code,
            currency=c.currency, status=c.launch_status,
        )
        for c in visible_cities()
    ]
