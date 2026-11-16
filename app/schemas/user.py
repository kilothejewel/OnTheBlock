from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    identifier: str = Field(..., description="Email address or username")
    password: str


class UserResponse(BaseModel):
    id: int
    username: Optional[str] = None  # empty for a guest
    email: Optional[EmailStr] = None
    is_guest: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_guest: bool = False
    claimed_chats: int = 0  # chats kept from a guest session on sign-up or log-in (#125)
