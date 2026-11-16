"""
What the LLM steps take and return (app/services/llm.py, ADR 0006).

Intake turns a chat into a patch of what the user wants plus the next
action; compose picks one candidate per Slot and writes the copy. The intake
fields are the ones the Brief (#87) is built from; #91 maps them onto it.
"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(max_length=4000)


class IntakePatch(BaseModel):
    """What this turn says about the Plan; None means "not mentioned"."""

    model_config = ConfigDict(extra="forbid")
    interests: List[str] = Field(default_factory=list)  # keys from app/data/interests.yaml
    budget_zar: Optional[int] = Field(None, ge=0, le=1_000_000)
    date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    mode: Optional[Literal["day_out", "night_out"]] = None
    area: Optional[str] = Field(None, max_length=100)
    group_size: Optional[int] = Field(None, ge=1, le=50)


class LLMMeta(BaseModel):
    """Which provider answered and what it cost in quota, for the planner trace (#105)."""

    provider: str  # "gemini", "groq" or "rules"
    model: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0
    fallbacks: List[str] = Field(default_factory=list)  # e.g. ["gemini:quota", "groq:timeout"]


class IntakeResult(BaseModel):
    patch: IntakePatch
    next_action: Literal["ask", "plan", "off_topic"]
    question: Optional[str] = None  # what to ask next, when next_action is "ask"
    meta: LLMMeta


class SkeletonSlot(BaseModel):
    slot_id: str = Field(pattern=r"^s\d+$")
    kind: str  # breakfast, lunch, dinner, activity, nightlife
    start: str  # "09:00"
    interest: Optional[str] = None


class Candidate(BaseModel):
    key: str = Field(pattern=r"^s\d+c\d+$")  # what compose picks; mapped to a place ID in code
    name: str
    category: Optional[str] = None
    area: Optional[str] = None
    snippet: Optional[str] = None  # a line of guide text, with its source shown separately
    score: float = 0


class ComposedStop(BaseModel):
    slot_id: str
    candidate_key: str
    title: str = Field(max_length=120)
    description: str = Field(max_length=600)


class ComposeResult(BaseModel):
    intro: str = Field(max_length=600)
    stops: List[ComposedStop]
    meta: LLMMeta

    def by_slot(self) -> Dict[str, ComposedStop]:
        return {stop.slot_id: stop for stop in self.stops}
