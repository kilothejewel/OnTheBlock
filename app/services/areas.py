"""
Areas: the neighbourhoods of each city a Plan can stay inside (GLOSSARY: Area).

One file per city, app/data/areas/<city>.yaml, named by the city's
`areas_file` in the registry (#85). Each file is validated when first read;
a city whose file doesn't exist yet simply has no Areas. Every Area's
centre must lie inside its city's bounds.
"""

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional, Tuple

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.cities import CITIES, City


class AreasFileError(ValueError):
    """An Areas file is invalid."""


class _Point(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class _AreaEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    name: str = Field(min_length=1)
    centre: _Point
    radius_m: int = Field(gt=0, le=20000)
    walk_friendly: bool = False
    night_safe: bool = False
    aliases: List[str] = Field(default_factory=list)
    notes: str = ""
    reviewed: bool = False


class _AreasFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    areas: List[_AreaEntry] = Field(min_length=1)


@dataclass(frozen=True)
class Area:
    slug: str
    name: str
    lat: float
    lng: float
    radius_m: int
    walk_friendly: bool  # walking between nearby Stops is fine by day (#97)
    night_safe: bool  # walking between Stops after dark is fine (#99); false when unsure
    aliases: Tuple[str, ...]
    notes: str
    reviewed: bool  # checked by a local

    def distance_m(self, lat: float, lng: float) -> float:
        """Great-circle distance from the Area's centre, in metres."""
        r = 6_371_000
        p1, p2 = math.radians(self.lat), math.radians(lat)
        dp, dl = p2 - p1, math.radians(lng - self.lng)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * r * math.asin(math.sqrt(a))

    def contains(self, lat: float, lng: float) -> bool:
        return self.distance_m(lat, lng) <= self.radius_m


def load_areas(city: City, path=None) -> List[Area]:
    """The city's Areas, validated; [] while its file doesn't exist yet."""
    path = path or city.areas_path
    if path is None:
        return []
    try:
        raw = yaml.safe_load(open(path, encoding="utf-8").read())
        entries = _AreasFile.model_validate(raw).areas
    except yaml.YAMLError as exc:
        raise AreasFileError(f"{path} isn't valid YAML: {exc}")
    except ValidationError as exc:
        problems = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        raise AreasFileError(f"{path} is invalid:\n  " + "\n  ".join(problems))

    slugs = [e.slug for e in entries]
    duplicates = sorted({s for s in slugs if slugs.count(s) > 1})
    if duplicates:
        raise AreasFileError(f"{path} has duplicate Area slugs: {', '.join(duplicates)}")
    outside = [e.slug for e in entries if not city.contains(e.centre.lat, e.centre.lng)]
    if outside:
        raise AreasFileError(f"{path}: these Areas' centres are outside {city.name}'s bounds: {', '.join(outside)}")

    return [
        Area(slug=e.slug, name=e.name, lat=e.centre.lat, lng=e.centre.lng, radius_m=e.radius_m,
             walk_friendly=e.walk_friendly, night_safe=e.night_safe, aliases=tuple(e.aliases),
             notes=e.notes, reviewed=e.reviewed)
        for e in entries
    ]


@lru_cache(maxsize=None)
def areas_for(city_slug: str) -> Tuple[Area, ...]:
    """A city's Areas, read once per process."""
    return tuple(load_areas(CITIES[city_slug]))


def find_area(city_slug: str, text: str) -> Optional[Area]:
    """The Area a name or alias refers to ("Obs", "the Waterfront"), case-insensitively."""
    wanted = " ".join((text or "").lower().replace("the ", " ").split())
    for area in areas_for(city_slug):
        names = {area.slug.replace("-", " "), area.name.lower(), *(a.lower() for a in area.aliases)}
        if wanted in {" ".join(n.replace("the ", " ").split()) for n in names}:
            return area
    return None


def area_at(city_slug: str, lat: float, lng: float) -> Optional[Area]:
    """The nearest Area whose radius covers the point."""
    inside = [a for a in areas_for(city_slug) if a.contains(lat, lng)]
    return min(inside, key=lambda a: a.distance_m(lat, lng)) if inside else None
