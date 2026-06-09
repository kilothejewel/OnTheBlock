from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.hotspot import Hotspot
from app.schemas.hotspot import HotspotCreate, HotspotResponse
from app.services.places import places_service

router = APIRouter(prefix="/hotspots", tags=["hotspots"])

@router.get("/recommend", response_model=List[HotspotCreate])
async def recommend_hotspots(
    query: str,
    current_user: User = Depends(get_current_user)
):
    """
    Search and retrieve recommended hotspots from Google Places API.
    """
    try:
        places = await places_service.search_places(query)
        return places
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch recommendations: {str(e)}"
        )

@router.post("/", response_model=HotspotResponse, status_code=status.HTTP_201_CREATED)
def save_hotspot(
    hotspot_in: HotspotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Save a hotspot to the current user's favorites.
    """
    # 1. Check if hotspot already exists in hotspots table
    hotspot = db.query(Hotspot).filter(Hotspot.google_place_id == hotspot_in.google_place_id).first()
    if not hotspot:
        hotspot = Hotspot(**hotspot_in.model_dump())
        db.add(hotspot)
        db.flush()  # Populates id without committing

    # 2. Link hotspot to user if not already linked
    if hotspot not in current_user.saved_hotspots:
        current_user.saved_hotspots.append(hotspot)
        db.commit()
    else:
        db.commit()

    db.refresh(hotspot)
    return hotspot

@router.get("/", response_model=List[HotspotResponse])
def list_saved_hotspots(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all hotspots saved by the current authenticated user.
    """
    return current_user.saved_hotspots

@router.delete("/{google_place_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_hotspot(
    google_place_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Remove a hotspot from the current user's favorites.
    """
    hotspot = db.query(Hotspot).filter(Hotspot.google_place_id == google_place_id).first()
    if not hotspot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotspot not found"
        )

    if hotspot in current_user.saved_hotspots:
        current_user.saved_hotspots.remove(hotspot)
        db.commit()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hotspot not saved by this user"
        )
    return
