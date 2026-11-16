"""
Interests: what people say they want ("hiking", "a jol", "wine farms"),
mapped to the categories Google, Overture and Foursquare use.

Loaded from app/data/interests.yaml when imported; an invalid file stops
startup. `match_interests` is the quick, LLM-free matcher: whole words and
phrases only, so "barbecue" never matches bars.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

INTERESTS_FILE = Path(__file__).resolve().parents[1] / "data" / "interests.yaml"

TimeOfDay = Literal["morning", "afternoon", "evening", "late_night"]
SlotKind = Literal["breakfast", "lunch", "dinner", "activity", "nightlife"]


class InterestsFileError(ValueError):
    """app/data/interests.yaml is missing or invalid."""


class _Entry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=10)
    synonyms: List[str] = Field(min_length=1)
    included_types: List[str] = Field(min_length=1)
    text_queries: List[str] = Field(min_length=1)
    overture_categories: List[str] = Field(min_length=1)
    fsq_category_ids: List[str] = Field(min_length=1)
    time_of_day: List[TimeOfDay] = Field(min_length=1)
    outdoor: bool
    typical_minutes: int = Field(gt=0, le=600)
    slot_kinds: List[SlotKind] = Field(min_length=1)
    min_reviews: Optional[int] = Field(None, ge=0)


@dataclass(frozen=True)
class Interest:
    key: str
    description: str
    synonyms: Tuple[str, ...]
    included_types: Tuple[str, ...]
    text_queries: Tuple[str, ...]
    overture_categories: Tuple[str, ...]
    fsq_category_ids: Tuple[str, ...]
    time_of_day: Tuple[str, ...]
    outdoor: bool
    typical_minutes: int
    slot_kinds: Tuple[str, ...]
    min_reviews: Optional[int] = None


def load_interests(path: Path = INTERESTS_FILE) -> Dict[str, Interest]:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise InterestsFileError(f"{path} is missing")
    except yaml.YAMLError as exc:
        raise InterestsFileError(f"{path} isn't valid YAML: {exc}")
    if not isinstance(raw, dict) or not isinstance(raw.get("interests"), dict) or not raw["interests"]:
        raise InterestsFileError(f"{path} must have a non-empty `interests:` mapping")

    interests, problems = {}, []
    for key, entry in raw["interests"].items():
        if not re.fullmatch(r"[a-z]+(_[a-z]+)*", str(key)):
            problems.append(f"{key}: keys are lower_snake_case")
            continue
        try:
            spec = _Entry.model_validate(entry)
        except ValidationError as exc:
            problems += [f"{key}.{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
            continue
        interests[key] = Interest(
            key=key, description=spec.description,
            synonyms=tuple(s.lower() for s in spec.synonyms),
            included_types=tuple(spec.included_types), text_queries=tuple(spec.text_queries),
            overture_categories=tuple(spec.overture_categories), fsq_category_ids=tuple(spec.fsq_category_ids),
            time_of_day=tuple(spec.time_of_day), outdoor=spec.outdoor, typical_minutes=spec.typical_minutes,
            slot_kinds=tuple(spec.slot_kinds), min_reviews=spec.min_reviews,
        )
    if problems:
        raise InterestsFileError(f"{path} is invalid:\n  " + "\n  ".join(problems))
    return interests


def _phrase_pattern(phrase: str) -> str:
    """A synonym as a whole-word pattern: words may be split by spaces or hyphens, plurals allowed."""
    words = [re.escape(word) for word in re.split(r"[\s-]+", phrase.strip())]
    return r"[\s-]+".join(words) + r"(?:s|es)?"


def _compile(interests: Dict[str, Interest]) -> Dict[str, re.Pattern]:
    patterns = {}
    for key, interest in interests.items():
        # The Interest's own name counts too ("live music" for live_music).
        phrases = sorted({*interest.synonyms, key.replace("_", " ")}, key=len, reverse=True)
        patterns[key] = re.compile(r"(?<![\w'])(?:" + "|".join(_phrase_pattern(p) for p in phrases) + r")(?![\w'])")
    return patterns


INTERESTS: Dict[str, Interest] = load_interests()
_PATTERNS = _compile(INTERESTS)


def match_interests(text: Optional[str]) -> List[Tuple[str, float]]:
    """
    The Interests a message mentions, strongest first, as (key, weight).

    Each mention of a synonym counts once; weights are scaled so the most
    mentioned Interest is 1.0. Whole words and phrases only, case-insensitive.
    """
    text = (text or "").lower()
    if not text.strip():
        return []
    counts = {}
    for key, pattern in _PATTERNS.items():
        hits = len(pattern.findall(text))
        if hits:
            counts[key] = hits
    if not counts:
        return []
    top = max(counts.values())
    order = list(INTERESTS)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], order.index(item[0])))
    return [(key, round(hits / top, 3)) for key, hits in ranked]


def wants_slot(text: Optional[str], slot_kind: str) -> bool:
    """Whether the message asks for an Interest that fills this kind of Slot, e.g. "nightlife"."""
    return any(slot_kind in INTERESTS[key].slot_kinds for key, _ in match_interests(text))
