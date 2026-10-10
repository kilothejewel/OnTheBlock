from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.rate_limit import limiter
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.place import PlacePhoto
from app.services.places import PlacesError, places_service

router = APIRouter(prefix="/places", tags=["places"])


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
        print(f"Photo lookup failed for {place_id}: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Couldn't load the photo.")
    if photo is None or not photo.get("url"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No photo for this place.")
    return photo
