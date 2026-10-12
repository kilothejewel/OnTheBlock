from typing import Optional

from pydantic import BaseModel


class PlacePhoto(BaseModel):
    url: str
    attribution: Optional[str] = None  # photographer's name, shown with the photo
    attribution_url: Optional[str] = None
