from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from typing import List, Any
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import get_current_user
from app.models.user import User
from app.models.itinerary import Itinerary
from app.schemas.itinerary import ItineraryCreate, ItineraryResponse, ItineraryGenerate
from app.services.itinerary import itinerary_service

router = APIRouter(prefix="/itineraries", tags=["itineraries"])

@router.post("/generate", response_model=Any)
@limiter.limit("5/minute")
async def generate_itinerary(
    request: Request,
    response: Response,
    params: ItineraryGenerate,
    current_user: User = Depends(get_current_user)
):
    """
    Generate an AI travel itinerary based on target destination, budget, and vibes.
    This does NOT save it to the DB immediately, allowing client previews first.

    Rate limited to 5 requests/minute per client: each call fans out to OpenAI and
    multiple Google Places lookups, making it the most expensive route in the API.
    """
    try:
        itinerary = await itinerary_service.generate_itinerary(params)
        return itinerary
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate itinerary: {str(e)}"
        )

@router.post("/", response_model=ItineraryResponse, status_code=status.HTTP_201_CREATED)
def save_itinerary(
    itinerary_in: ItineraryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Save a generated itinerary to the user's account.
    """
    itinerary = Itinerary(
        user_id=current_user.id,
        title=itinerary_in.title,
        destination=itinerary_in.destination,
        budget=itinerary_in.budget,
        duration_days=itinerary_in.duration_days,
        items=itinerary_in.items
    )
    db.add(itinerary)
    db.commit()
    db.refresh(itinerary)
    return itinerary

@router.get("/", response_model=List[ItineraryResponse])
def list_saved_itineraries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all itineraries saved by the current authenticated user.
    """
    return db.query(Itinerary).filter(Itinerary.user_id == current_user.id).order_by(Itinerary.created_at.desc()).all()

@router.get("/{itinerary_id}", response_model=ItineraryResponse)
def get_itinerary_details(
    itinerary_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve details of a specific saved itinerary.
    """
    itinerary = db.query(Itinerary).filter(
        Itinerary.id == itinerary_id, 
        Itinerary.user_id == current_user.id
    ).first()
    
    if not itinerary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Itinerary not found or unauthorized to view"
        )
    return itinerary

@router.delete("/{itinerary_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_itinerary(
    itinerary_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a saved itinerary.
    """
    itinerary = db.query(Itinerary).filter(
        Itinerary.id == itinerary_id, 
        Itinerary.user_id == current_user.id
    ).first()
    
    if not itinerary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Itinerary not found or unauthorized to delete"
        )
    
    db.delete(itinerary)
    db.commit()
    return
