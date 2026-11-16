from typing import List, Literal, Optional

from pydantic import BaseModel


class PlaceDetails(BaseModel):
    """
    What a saved Plan or place shows for a place ID (#29). From Google when
    `source` is "google"; otherwise from our catalogue ("catalogue") or Demo
    data ("demo"), with `details_available` false when Google wasn't asked.
    """

    google_place_id: str
    name: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    types: List[str] = []
    maps_url: Optional[str] = None
    area: Optional[str] = None  # Area slug from our catalogue
    source: Literal["google", "catalogue", "demo", "unknown"]
    details_available: bool


class PlacePhoto(BaseModel):
    url: str
    attribution: Optional[str] = None  # photographer's name, shown with the photo
    attribution_url: Optional[str] = None
