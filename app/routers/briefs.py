from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ValidationError

from app.schemas.brief import Brief, BriefError, BriefPatch, apply_patch, readable_errors

router = APIRouter(prefix="/briefs", tags=["briefs"])


class BriefUpdate(BaseModel):
    brief: dict
    patch: BriefPatch


@router.post("/check", response_model=Brief)
def check_brief(brief: dict) -> Brief:
    """
    Validate a Brief and return it with its defaults filled in. 422 lists what's
    wrong in plain words. No Google or LLM calls; open to everyone.
    """
    try:
        return Brief.model_validate(brief)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=readable_errors(exc))


@router.post("/apply", response_model=Brief)
def apply_brief_patch(update: BriefUpdate) -> Brief:
    """Apply a BriefPatch to a Brief: only the patch's fields change."""
    try:
        brief = Brief.model_validate(update.brief)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=readable_errors(exc))
    try:
        return apply_patch(brief, update.patch)
    except BriefError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.messages)
