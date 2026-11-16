import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.errors import ServiceUnavailable
from app.core.rate_limit import limiter
from app.core.security import get_current_user
from app.models.user import User
from app.models.itinerary import Itinerary
from app.schemas.itinerary import GeneratedItinerary, ItineraryCreate, ItineraryResponse, ItineraryGenerate
from app.services.itinerary import itinerary_service
from app.services.plan_quota import give_back_plan, take_plan
from app.core.observability import call_summary

log = logging.getLogger(__name__)

router = APIRouter(prefix="/itineraries", tags=["itineraries"])

@router.post("/generate", response_model=GeneratedItinerary)
@limiter.limit("5/minute")
async def generate_itinerary(
    request: Request,
    response: Response,
    params: ItineraryGenerate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate an AI travel itinerary based on target destination, budget, and vibes.
    This does NOT save it to the DB immediately, allowing client previews first.

    Rate limited to 5 requests/minute per user: each call fans out to OpenAI and
    multiple Google Places lookups, making it the most expensive route in the API.
    Each user can also start only OTB_PLANS_PER_USER_PER_DAY Plans a UTC day;
    past that it's a 429 saying when the quota resets.
    """
    quota = take_plan(db, current_user)
    if not quota.allowed:
        log.info("daily plan quota reached", extra={"limit": quota.limit})
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(quota.retry_after_seconds)},
            content={
                "detail": f"You've made {quota.limit} Plans today, your daily limit. You can make more from 00:00 UTC.",
                "limit": quota.limit,
                "resets_at": quota.resets_at.isoformat(),
            },
        )
    try:
        itinerary = await itinerary_service.generate_itinerary(params)
        log.info("plan generated", extra={"city": params.city, "demo": bool(itinerary.get("demo")), **call_summary()})
        return itinerary
    except ServiceUnavailable as e:
        give_back_plan(db, current_user, quota.day)
        log.warning("plan generation unavailable", extra={"city": params.city, "code": e.code, **call_summary()})
        raise
    except Exception as e:
        give_back_plan(db, current_user, quota.day)
        log.warning("plan generation failed", extra={"city": params.city, "error": str(e), **call_summary()})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Couldn't plan that day. Please try again."
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
        city=itinerary_in.city,
        currency=itinerary_in.currency,
        items=[stop.model_dump() for stop in itinerary_in.items]
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
