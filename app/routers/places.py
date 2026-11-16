import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import get_current_user
from app.models.user import User
from typing import List

from app.schemas.place import PlaceDetails, PlacePhoto
from app.services.places import MAX_DETAILS_IDS, PlacesError, places_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/places", tags=["places"])


@router.get("", response_model=List[PlaceDetails])
@limiter.limit("30/minute")
async def get_places(
    request: Request,
    response: Response,
    ids: str = Query(..., description="Comma-separated Google place IDs, up to 20"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Display details for the places of a saved Plan or Saved places, in one
    request: name, address, location and types (Place Details Pro). No rating,
    hours or price; no photo (that's /places/{id}/photo, when a Stop is opened).
    Quota refused or Google down: our catalogue's name and Area instead.
    """
    place_ids = [i.strip() for i in ids.split(",") if i.strip()]
    if not place_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Give at least one place ID.")
    if len(set(place_ids)) > MAX_DETAILS_IDS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"At most {MAX_DETAILS_IDS} place IDs per request.")
    return await places_service.get_details(place_ids, db)


@router.get("/{place_id}/photo", response_model=PlacePhoto)
@limiter.limit("120/minute")
async def get_place_photo(
    request: Request,
    response: Response,
    place_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    A place's main Google photo: a short-lived image URL plus the photographer
    credit Google requires us to show. 404 when the place has no photo (or the
    app is running on demo data). The API key never reaches the browser.
    """
    try:
        photo = await places_service.get_photo(place_id)
    except PlacesError as e:
        log.warning("photo lookup failed", extra={"place_id": place_id, "error": str(e)})
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Couldn't load the photo.")
    if photo is None or not photo.get("url"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No photo for this place.")
    return photo
