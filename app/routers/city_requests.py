from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_actor
from app.models.city_request import CityRequest
from app.models.user import User

router = APIRouter(prefix="/city-requests", tags=["cities"])

REQUESTS_PER_DAY = 5


def utc_now() -> datetime:
    return datetime.utcnow()


class CityRequestIn(BaseModel):
    text: str = Field(max_length=80, description="What the person typed into the city search box.")

    @field_validator("text")
    @classmethod
    def _tidy(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Type the city you'd like us to cover.")
        return value


class CityRequestOut(BaseModel):
    id: int
    text: str
    created_at: datetime


@router.post("", response_model=CityRequestOut, status_code=status.HTTP_201_CREATED)
def request_city(payload: CityRequestIn, db: Session = Depends(get_db), actor: User = Depends(get_actor)) -> CityRequest:
    """
    Ask for a city we don't cover yet, from the city search box (#89). For
    accounts and guests, at most 5 a day (UTC) per user.
    """
    now = utc_now()
    start_of_day = datetime.combine(now.date(), time.min)
    today = (
        db.query(CityRequest)
        .filter(CityRequest.user_id == actor.id, CityRequest.created_at >= start_of_day)
        .count()
    )
    if today >= REQUESTS_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"You've asked for {REQUESTS_PER_DAY} cities today. Try again tomorrow.",
            headers={"Retry-After": str(int((start_of_day + timedelta(days=1) - now).total_seconds()))},
        )
    row = CityRequest(text=payload.text, user_id=actor.id, created_at=now)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
