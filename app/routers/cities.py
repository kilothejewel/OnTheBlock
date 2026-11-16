from typing import List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.cities import CITIES, visible_cities
from app.services.areas import areas_for

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


class AreaOut(BaseModel):
    slug: str
    name: str
    lat: float
    lng: float
    radius_m: int
    walk_friendly: bool
    night_safe: bool
    aliases: List[str]
    reviewed: bool


@router.get("/{slug}/areas", response_model=List[AreaOut])
def list_areas(slug: str) -> List[AreaOut]:
    """
    A city's Areas, for picking where a Plan stays (GLOSSARY: Area). 404 for a
    city that isn't in the registry or isn't open for planning. Open to everyone.
    """
    city = CITIES.get(slug)
    if city is None or not city.visible:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="We don't plan in that city yet.")
    return [
        AreaOut(slug=a.slug, name=a.name, lat=a.lat, lng=a.lng, radius_m=a.radius_m, walk_friendly=a.walk_friendly,
                night_safe=a.night_safe, aliases=list(a.aliases), reviewed=a.reviewed)
        for a in areas_for(slug)
    ]
