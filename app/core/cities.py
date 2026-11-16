"""
The cities the app plans in, from app/data/cities.yaml.

The file is loaded and validated when this module is imported, so the API
won't start with a broken registry: CityRegistryError says which city and
field are wrong. Only `live` and `beta` cities take new Plans and searches
(`PlannableCity`); a `hidden` city's saved Plans still open.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Dict, List, Literal, Optional, Tuple

import yaml
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError, WithJsonSchema, model_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CITIES_FILE = DATA_DIR / "cities.yaml"

LaunchStatus = Literal["live", "beta", "hidden"]
VISIBLE_STATUSES = ("live", "beta")


class CityRegistryError(ValueError):
    """app/data/cities.yaml is missing or invalid."""


class _Point(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class _Bounds(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sw: _Point
    ne: _Point

    @model_validator(mode="after")
    def _corners_in_order(self):
        if not (self.sw.lat < self.ne.lat and self.sw.lng < self.ne.lng):
            raise ValueError("sw must be south-west of ne")
        return self


class _CityEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = Field(pattern=r"^[a-z]+(-[a-z]+)*$")
    name: str = Field(min_length=1)
    province: str = Field(min_length=1)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    timezone: str
    centre: _Point
    search_radius_m: int = Field(gt=0, le=50000)
    bounds: _Bounds
    launch_status: LaunchStatus
    areas_file: str = Field(pattern=r"^areas/[a-z-]+\.yaml$")
    usd_rate: float = Field(gt=0)
    aliases: List[str] = Field(default_factory=list)  # other names people search for, e.g. "Jozi"

    @model_validator(mode="after")
    def _checks(self):
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"unknown time zone {self.timezone!r}")
        b = self.bounds
        if not (b.sw.lat <= self.centre.lat <= b.ne.lat and b.sw.lng <= self.centre.lng <= b.ne.lng):
            raise ValueError("centre must be inside bounds")
        return self


class _Registry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cities: List[_CityEntry] = Field(min_length=1)


@dataclass(frozen=True)
class City:
    slug: str
    name: str
    province: str
    country_code: str  # ISO 3166-1 alpha-2, used as the Places regionCode
    currency: str  # ISO 4217 code that costs are estimated in
    timezone: str  # IANA zone: Plans' times are this city's clock
    lat: float  # centre
    lng: float
    radius_m: int  # search radius around the centre
    bounds: Tuple[Tuple[float, float], Tuple[float, float]]  # ((south, west), (north, east))
    launch_status: str
    areas_file: str  # relative to app/data
    usd_rate: float  # approximate units per US dollar, for Demo data cost estimates only
    aliases: Tuple[str, ...] = ()  # other names for the city search box (#89)

    @property
    def visible(self) -> bool:
        """Takes new Plans and searches (live or beta)."""
        return self.launch_status in VISIBLE_STATUSES

    @property
    def is_south_african(self) -> bool:
        return self.country_code == "ZA"

    @property
    def areas_path(self) -> Optional[Path]:
        """The Areas file (#35), or None while it doesn't exist."""
        path = DATA_DIR / self.areas_file
        return path if path.exists() else None

    def contains(self, lat: float, lng: float) -> bool:
        """Whether a point is inside the city's bounds."""
        (south, west), (north, east) = self.bounds
        return south <= lat <= north and west <= lng <= east

    @property
    def bounds_area(self) -> float:
        (south, west), (north, east) = self.bounds
        return (north - south) * (east - west)


def _city_label(raw, index: int) -> str:
    """'city cape-town' for the index-th entry, or 'city #3' when it has no slug."""
    entries = raw.get("cities") if isinstance(raw, dict) else None
    if isinstance(entries, list) and index < len(entries) and isinstance(entries[index], dict) and entries[index].get("slug"):
        return f"city {entries[index]['slug']}"
    return f"city #{index + 1}"


def load_cities(path: Path = CITIES_FILE) -> Dict[str, City]:
    """Read and validate the registry. Raises CityRegistryError with what's wrong."""
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CityRegistryError(f"{path} is missing")
    except yaml.YAMLError as exc:
        raise CityRegistryError(f"{path} isn't valid YAML: {exc}")
    try:
        registry = _Registry.model_validate(raw)
    except ValidationError as exc:
        problems = []
        for error in exc.errors():
            where = [str(part) for part in error["loc"]]
            if len(where) >= 2 and where[0] == "cities" and where[1].isdigit():
                where = [_city_label(raw, int(where[1]))] + where[2:]
            problems.append(f"{'.'.join(where) or 'file'}: {error['msg']}")
        raise CityRegistryError(f"{path} is invalid:\n  " + "\n  ".join(problems))

    slugs = [entry.slug for entry in registry.cities]
    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicates:
        raise CityRegistryError(f"{path} is invalid: duplicate slug {', '.join(duplicates)}")

    return {
        entry.slug: City(
            slug=entry.slug,
            name=entry.name,
            province=entry.province,
            country_code=entry.country_code,
            currency=entry.currency,
            timezone=entry.timezone,
            lat=entry.centre.lat,
            lng=entry.centre.lng,
            radius_m=entry.search_radius_m,
            bounds=((entry.bounds.sw.lat, entry.bounds.sw.lng), (entry.bounds.ne.lat, entry.bounds.ne.lng)),
            launch_status=entry.launch_status,
            areas_file=entry.areas_file,
            usd_rate=entry.usd_rate,
            aliases=tuple(entry.aliases),
        )
        for entry in registry.cities
    }


CITIES: Dict[str, City] = load_cities()

_STATUS_ORDER = {"live": 0, "beta": 1}


def visible_cities() -> List[City]:
    """Cities that take new Plans, in picker order: South Africa first (live, then beta), then the rest."""
    visible = [city for city in CITIES.values() if city.visible]
    position = {slug: index for index, slug in enumerate(CITIES)}
    return sorted(visible, key=lambda c: (not c.is_south_african, _STATUS_ORDER[c.launch_status], position[c.slug]))


def get_city(slug: str) -> City:
    return CITIES[slug]


def city_at(lat: float, lng: float) -> Optional[City]:
    """The city a point is in: where bounds overlap, the smallest (Stellenbosch, not Cape Town)."""
    matches = [city for city in CITIES.values() if city.contains(lat, lng)]
    return min(matches, key=lambda c: c.bounds_area) if matches else None


def _known_city(slug: str) -> str:
    if slug not in CITIES:
        raise ValueError(f"Unknown city {slug!r}")
    return slug


def _plannable_city(slug: str) -> str:
    _known_city(slug)
    if not CITIES[slug].visible:
        raise ValueError(f"{CITIES[slug].name} isn't open for planning yet")
    return slug


# Any city in the registry, e.g. on a saved Plan.
CitySlug = Annotated[
    str, AfterValidator(_known_city),
    WithJsonSchema({"type": "string", "enum": list(CITIES)}),
]
# A city that takes new Plans and searches (live or beta); hidden ones get a 422.
PlannableCity = Annotated[
    str, AfterValidator(_plannable_city),
    WithJsonSchema({"type": "string", "enum": [city.slug for city in visible_cities()]}),
]
