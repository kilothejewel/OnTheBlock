"""
The cost model (#96): a per-person range for every Stop, in the city's currency.

`estimate_stop(place, slot, city)` tries, in order:

1. the city's fee table (by Google place ID once known, else name + Area)
2. Google `priceRange` from the live check, when that Stop was confirmed
   (converted only if it isn't in the city's currency)
3. Google `priceLevel` from the live check -> a band for the Slot kind
4. the catalogue category -> a band
5. the Slot kind's default band

using `app/data/costs/<city>.yaml` (#95), then the shared `_default.yaml`
(marked `beta_estimate`, so the UI says "rough estimate"). When nothing is
known the basis is `unknown` and the UI says "price not confirmed": no
amount is ever made up, and no cost lives in this code.

Google price fields are used for this estimate only and are never stored.
Every file is validated when this module is imported: a bad row stops the
API from starting, naming the file and the row.
"""

import logging
import math
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional, Tuple

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.core.cities import CITIES, City

log = logging.getLogger(__name__)

COSTS_DIR = Path(__file__).resolve().parents[1] / "data" / "costs"
DEFAULT_FILE = "_default.yaml"

Basis = Literal["fee_table", "google_price_range", "google_price_level", "category_band", "default", "beta_estimate", "unknown"]
BASES: Tuple[str, ...] = Basis.__args__

# Slot kinds a band can be given for: the planner's Slots plus the finer ones the data uses.
BAND_SLOTS = ("breakfast", "coffee", "lunch", "dinner", "drinks", "activity", "nightlife")
# Amounts are rounded to what people quote: R10, ¥100, else whole units.
ROUND_TO = {"ZAR": 10, "JPY": 100}
GOOGLE_PRICE_LEVELS = {
    "PRICE_LEVEL_FREE": 0, "PRICE_LEVEL_INEXPENSIVE": 1, "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3, "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}


class CostFileError(ValueError):
    """A file in app/data/costs is missing or invalid."""


@dataclass(frozen=True)
class Cost:
    """Per person, whole units of the city's currency. min and max are None when unknown."""

    min: Optional[int]
    max: Optional[int]
    basis: str

    @property
    def known(self) -> bool:
        return self.min is not None


UNKNOWN = Cost(None, None, "unknown")

# ---------------------------------------------------------------- the files

Band = Optional[Tuple[float, float]]


def _band(value: Any) -> Band:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, list, tuple)):
        raise ValueError(f"expected [min, max], a number or null, got {value!r}")
    low, high = (value, value) if isinstance(value, (int, float)) else tuple(value) if len(value) == 2 else (None, None)
    if low is None or not all(isinstance(n, (int, float)) and not isinstance(n, bool) for n in (low, high)):
        raise ValueError(f"expected [min, max], got {value!r}")
    if not 0 <= low <= high:
        raise ValueError(f"needs 0 <= min <= max, got {value!r}")
    return (float(low), float(high))


class _Sourced(BaseModel):
    """A section or row: amounts only with a source and the date it was checked (#95)."""

    model_config = ConfigDict(extra="forbid")
    todo: Optional[str] = None
    source_url: Optional[str] = None
    checked_on: Optional[date] = None

    def _require_source(self, has_amounts: bool) -> None:
        if has_amounts and not (self.source_url and self.checked_on):
            raise ValueError("has amounts but no source_url and checked_on")


class _Fee(_Sourced):
    key: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    name: str
    value: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None
    place_id: Optional[str] = None  # Google place ID, once matched
    match_names: List[str] = Field(default_factory=list)  # names a Stop may go by
    area: Optional[str] = None  # Area slug the names must be in

    @model_validator(mode="after")
    def _sourced(self):
        self._require_source(self.value is not None)
        return self


class _Bands(_Sourced):
    """`name: [min, max]` rows (or a single amount, or null) plus the source fields."""

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def _rows(self):
        rows = {}
        for name, value in (self.model_extra or {}).items():
            try:
                rows[str(name)] = _band(value)
            except ValueError as exc:
                raise ValueError(f"{name}: {exc}")
        object.__setattr__(self, "rows", rows)
        self._require_source(any(b is not None for b in rows.values()))
        return self


class _PriceLevelBands(_Sourced):
    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def _rows(self):
        rows: Dict[str, Dict[int, Band]] = {}
        for slot, levels in (self.model_extra or {}).items():
            if slot not in BAND_SLOTS:
                raise ValueError(f"{slot}: unknown Slot kind (use one of {', '.join(BAND_SLOTS)})")
            if not isinstance(levels, dict) or not set(levels) <= {0, 1, 2, 3, 4}:
                raise ValueError(f"{slot}: expected price levels 0-4")
            try:
                rows[slot] = {int(level): _band(band) for level, band in levels.items()}
            except ValueError as exc:
                raise ValueError(f"{slot}: {exc}")
        object.__setattr__(self, "rows", rows)
        self._require_source(any(b is not None for levels in rows.values() for b in levels.values()))
        return self


class _CostFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    city: str
    currency: Optional[str] = Field(None, pattern=r"^[A-Z]{3}$")
    fees: List[_Fee] = Field(default_factory=list)
    price_level_bands: _PriceLevelBands
    category_bands: _Bands
    defaults: _Bands
    e_hailing: _Bands  # transport legs (#97)
    parking: _Bands

    @field_validator("defaults")
    @classmethod
    def _slot_defaults(cls, value: _Bands) -> _Bands:
        unknown = sorted(set(value.rows) - set(BAND_SLOTS))
        if unknown:
            raise ValueError(f"{', '.join(unknown)}: defaults are per Slot kind ({', '.join(BAND_SLOTS)})")
        return value

    @model_validator(mode="after")
    def _currency_when_priced(self):
        priced = any(f.value is not None for f in self.fees) or any(
            b is not None
            for section in (self.category_bands, self.defaults)
            for b in section.rows.values()
        ) or any(b is not None for levels in self.price_level_bands.rows.values() for b in levels.values())
        if priced and not self.currency:
            raise ValueError("currency: needed once the file has amounts")
        return self


def _row_label(raw: Any, loc: Tuple[Any, ...]) -> str:
    """'fees[kirstenbosch].value' rather than 'fees.1.value'."""
    parts: List[str] = []
    node = raw
    for part in loc:
        if isinstance(node, list) and isinstance(part, int) and part < len(node):
            node = node[part]
            key = node.get("key") if isinstance(node, dict) else None
            parts[-1] = f"{parts[-1]}[{key or part}]" if parts else f"[{key or part}]"
            continue
        parts.append(str(part))
        node = node.get(part) if isinstance(node, dict) else None
    return ".".join(parts) or "file"


def load_cost_file(path: Path) -> _CostFile:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CostFileError(f"{path} is missing")
    except yaml.YAMLError as exc:
        raise CostFileError(f"{path} isn't valid YAML: {exc}")
    try:
        return _CostFile.model_validate(raw)
    except ValidationError as exc:
        problems = []
        for error in exc.errors():
            loc = tuple(p for p in error["loc"] if p not in ("function-after",))
            message = error["msg"].removeprefix("Value error, ")
            problems.append(f"{_row_label(raw, loc)}: {message}")
        raise CostFileError(f"{path} is invalid:\n  " + "\n  ".join(problems))


def load_costs(directory: Path = COSTS_DIR) -> Dict[str, _CostFile]:
    """Every city's file plus `_default`, keyed by city slug. Raises CostFileError."""
    files = {}
    for path in sorted(Path(directory).glob("*.yaml")):
        data = load_cost_file(path)
        if data.city != path.stem:
            raise CostFileError(f"{path} is invalid:\n  city: should be {path.stem!r}, the file's name")
        if path.stem != "_default" and path.stem not in CITIES:
            raise CostFileError(f"{path} is invalid:\n  city: {path.stem!r} isn't in app/data/cities.yaml")
        files[path.stem] = data
    if "_default" not in files:
        raise CostFileError(f"{Path(directory) / DEFAULT_FILE} is missing")
    return files


COSTS: Dict[str, _CostFile] = load_costs()

# ---------------------------------------------------------------- estimating


def _fold(text: Optional[str]) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).lower().replace("'", "").replace("’", "").split())


def _round(amount: float, currency: str) -> int:
    step = ROUND_TO.get(currency, 1)
    return int(math.floor(amount / step + 0.5) * step)  # halves round up: R85 -> R90


def _cost(low: float, high: float, basis: str, city: City, rate: float = 1.0) -> Cost:
    low_r, high_r = _round(low * rate, city.currency), _round(high * rate, city.currency)
    return Cost(max(0, low_r), max(0, low_r, high_r), basis)


def _rate(file_currency: Optional[str], city: City) -> Optional[float]:
    """Multiplier from a file's currency to the city's, or None when it can't convert."""
    if file_currency in (None, city.currency):
        return 1.0
    if file_currency == "USD":
        return city.usd_rate
    return None


def _price_level(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and 0 <= value <= 4:
        return value
    return GOOGLE_PRICE_LEVELS.get(value) if isinstance(value, str) else None


def _money(price: Any) -> Optional[Tuple[str, float]]:
    """A Google Money object ({currencyCode, units, nanos}) as (currency, amount)."""
    if not isinstance(price, Mapping) or not price.get("currencyCode"):
        return None
    try:
        return price["currencyCode"], float(price.get("units") or 0) + float(price.get("nanos") or 0) / 1e9
    except (TypeError, ValueError):
        return None


def _from_price_range(price_range: Any, city: City) -> Optional[Cost]:
    if not isinstance(price_range, Mapping):
        return None
    start, end = _money(price_range.get("startPrice")), _money(price_range.get("endPrice"))
    if start is None:
        return None
    end = end or start  # open-ended ("R500+"): the start is all we know
    if start[0] != end[0]:
        return None
    currency = start[0]
    rate = _rate(currency, city)
    if rate is None:
        log.info("Google price range in a currency we can't convert", extra={"from": currency, "to": city.currency})
        return None
    if currency != city.currency:
        log.info("converted a Google price range", extra={"from": currency, "to": city.currency})
    return _cost(start[1], end[1], "google_price_range", city, rate)


def _fee(data: _CostFile, place: Mapping[str, Any], city: City) -> Optional[Cost]:
    place_id, name, area = place.get("google_place_id"), _fold(place.get("name")), place.get("area")
    for fee in data.fees:
        by_id = fee.place_id is not None and fee.place_id == place_id
        by_name = (
            fee.place_id is None or not place_id
        ) and name and any(_fold(n) in name for n in fee.match_names) and (fee.area is None or fee.area == area)
        if by_id or by_name:
            if fee.value is None:
                return None  # known place, price still to check: fall through
            rate = _rate(data.currency, city)
            return _cost(fee.value, fee.value, "fee_table", city, rate) if rate is not None else None
    return None


def _categories(place: Mapping[str, Any]) -> List[str]:
    found = list(place.get("categories") or [])
    if place.get("category"):
        found.append(place["category"])
    return [str(c) for c in found]


def _bands(data: _CostFile, place: Mapping[str, Any], slot: str, use_google: bool, city: City) -> Optional[Cost]:
    """Levels 3-5 from one file: Google price level, category, Slot default."""
    rate = _rate(data.currency, city)
    if rate is None:
        return None
    candidates: List[Tuple[Band, str]] = []
    level = _price_level(place.get("price_level")) if use_google else None
    if level is not None:
        candidates.append((data.price_level_bands.rows.get(slot, {}).get(level), "google_price_level"))
    for category in _categories(place):
        candidates.append((data.category_bands.rows.get(category), "category_band"))
    candidates.append((data.defaults.rows.get(slot), "default"))
    for band, basis in candidates:
        if band is not None:
            return _cost(band[0], band[1], basis, city, rate)
    return None


def estimate_stop(place: Mapping[str, Any], slot: str, city: City, costs: Optional[Dict[str, _CostFile]] = None) -> Cost:
    """
    The per-person cost of a Stop. `place` has whatever is known:
    `google_place_id`, `name`, `area` (slug), `categories` / `category`, and
    from the live check (#93) `confirmed`, `price_level` and `price_range`.
    Google fields are ignored unless `confirmed` is true.
    """
    costs = costs if costs is not None else COSTS
    confirmed = bool(place.get("confirmed"))
    own = costs.get(city.slug)
    if own is not None:
        found = _fee(own, place, city)
        if found:
            return found
    if confirmed:
        found = _from_price_range(place.get("price_range"), city)
        if found:
            return found
    if own is not None:
        found = _bands(own, place, slot, confirmed, city)
        if found:
            return found
    shared = costs["_default"]
    found = _bands(shared, place, slot, confirmed, city)
    if found:
        return Cost(found.min, found.max, "beta_estimate")
    return UNKNOWN
