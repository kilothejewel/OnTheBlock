"""
Build a city's places catalogue from open data (#119, ADR 0007).

    python -m scripts.catalogue.ingest --city cape-town

Runs in a GitHub Action (.github/workflows/catalogue.yml), never on the API
host. DuckDB reads only the rows inside the city's bounds straight from the
published GeoParquet:

- Overture Maps places (CDLA Permissive 2.0), release pinned in
  app/data/sources.yaml;
- Foursquare OS Places (Apache 2.0), when --fsq points at its files (the
  Hugging Face copy needs a token, so it's optional).

It keeps places whose category maps to an Interest (app/data/interests.yaml),
drops Overture rows below OTB_CATALOGUE_MIN_CONFIDENCE and closed places,
merges duplicates (normalised names >= 0.85 alike within 75 m) into one row
with both source ids, gives each its Area, and upserts the `places` table by
source id. A place missing from two releases in a row is deleted. Running the
same release again changes nothing.
"""

import argparse
import json
import logging
import math
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.cities import CITIES, City  # noqa: E402
from app.services.areas import area_at  # noqa: E402
from app.services.interests import INTERESTS  # noqa: E402

log = logging.getLogger("catalogue")

OVERTURE_S3 = "s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*"
MERGE_DISTANCE_M = 75
MERGE_NAME_SIMILARITY = 0.85


# --------------------------------------------------------------------------
# Rows
# --------------------------------------------------------------------------

@dataclass
class Row:
    """One place, from one or both sources."""

    name: str
    lat: float
    lng: float
    categories: List[str]
    interests: List[str]
    overture_id: Optional[str] = None
    fsq_id: Optional[str] = None
    confidence: Optional[float] = None
    website: Optional[str] = None
    area_id: Optional[str] = None
    merged: int = 0  # how many other rows were folded into this one


@dataclass
class Report:
    city: str
    release: str
    read: Dict[str, int] = field(default_factory=dict)
    dropped: Dict[str, int] = field(default_factory=dict)
    merged: int = 0
    kept: int = 0
    in_an_area: int = 0
    per_interest: Dict[str, int] = field(default_factory=dict)
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0
    table_bytes: Optional[int] = None

    def to_dict(self):
        return self.__dict__


def _category_maps() -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """Overture category -> Interests, Foursquare category id -> Interests."""
    overture, fsq = {}, {}
    for key, interest in INTERESTS.items():
        for category in interest.overture_categories:
            overture.setdefault(category, []).append(key)
        for category_id in interest.fsq_category_ids:
            fsq.setdefault(category_id, []).append(key)
    return overture, fsq


def _unique(values: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(v for v in values if v))


# --------------------------------------------------------------------------
# Reading with DuckDB
# --------------------------------------------------------------------------

def _connect(remote: bool):
    import duckdb

    con = duckdb.connect()
    if remote:
        con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
        token = os.environ.get("HF_TOKEN")
        if token:
            con.execute("CREATE SECRET hf (TYPE huggingface, TOKEN ?)", [token])
    return con


def read_overture(con, source: str, city: City, min_confidence: float, report: Report) -> List[Row]:
    """Overture rows inside the city's bounds that map to an Interest and are likely open."""
    (south, west), (north, east) = city.bounds
    rows = con.execute(
        f"""
        SELECT id, names.primary AS name, (bbox.ymin + bbox.ymax) / 2 AS lat, (bbox.xmin + bbox.xmax) / 2 AS lng,
               confidence, operating_status, taxonomy.primary AS category, taxonomy.alternates AS alternates,
               websites
        FROM read_parquet(?, hive_partitioning = true)
        WHERE bbox.xmin BETWEEN ? AND ? AND bbox.ymin BETWEEN ? AND ?
        """,
        [source, west, east, south, north],
    ).fetchall()
    overture_map, _ = _category_maps()
    report.read["overture"] = len(rows)
    kept = []
    for oid, name, lat, lng, confidence, status, category, alternates, websites in rows:
        if not name:
            report.dropped["overture_no_name"] = report.dropped.get("overture_no_name", 0) + 1
            continue
        if status in ("permanently_closed", "temporarily_closed"):
            report.dropped["closed"] = report.dropped.get("closed", 0) + 1
            continue
        if confidence is None or confidence < min_confidence:
            report.dropped["low_confidence"] = report.dropped.get("low_confidence", 0) + 1
            continue
        interests = overture_map.get(category or "")
        if not interests:
            report.dropped["unmapped_category"] = report.dropped.get("unmapped_category", 0) + 1
            continue
        kept.append(Row(
            name=name.strip(), lat=float(lat), lng=float(lng),
            categories=_unique([category, *(alternates or [])]), interests=_unique(interests),
            overture_id=oid, confidence=round(float(confidence), 3),
            website=(websites or [None])[0],
        ))
    return kept


def read_fsq(con, source: str, city: City, report: Report) -> List[Row]:
    """Foursquare OS Places rows inside the city's bounds that map to an Interest and aren't closed."""
    (south, west), (north, east) = city.bounds
    rows = con.execute(
        """
        SELECT fsq_place_id, name, latitude, longitude, fsq_category_ids, date_closed, website
        FROM read_parquet(?)
        WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?
        """,
        [source, south, north, west, east],
    ).fetchall()
    _, fsq_map = _category_maps()
    report.read["fsq"] = len(rows)
    kept = []
    for fid, name, lat, lng, category_ids, closed, website in rows:
        if closed:
            report.dropped["closed"] = report.dropped.get("closed", 0) + 1
            continue
        if not name:
            report.dropped["fsq_no_name"] = report.dropped.get("fsq_no_name", 0) + 1
            continue
        interests = _unique(i for cid in (category_ids or []) for i in fsq_map.get(cid, []))
        if not interests:
            report.dropped["unmapped_category"] = report.dropped.get("unmapped_category", 0) + 1
            continue
        kept.append(Row(
            name=name.strip(), lat=float(lat), lng=float(lng),
            categories=_unique(category_ids or []), interests=interests, fsq_id=fid, website=website,
        ))
    return kept


# --------------------------------------------------------------------------
# Merging
# --------------------------------------------------------------------------

_STOP_WORDS = {"the", "and", "restaurant", "cafe", "bar", "cape", "town", "pty", "ltd"}


def normalise_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text.replace("&", " and "))
    words = [w for w in text.split() if w not in _STOP_WORDS]
    return " ".join(words) or text.strip()


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def same_place(a: Row, b: Row) -> bool:
    if distance_m(a.lat, a.lng, b.lat, b.lng) > MERGE_DISTANCE_M:
        return False
    return SequenceMatcher(None, normalise_name(a.name), normalise_name(b.name)).ratio() >= MERGE_NAME_SIMILARITY


def _fold(keep: Row, other: Row) -> None:
    keep.overture_id = keep.overture_id or other.overture_id
    keep.fsq_id = keep.fsq_id or other.fsq_id
    keep.categories = _unique([*keep.categories, *other.categories])
    keep.interests = _unique([*keep.interests, *other.interests])
    keep.website = keep.website or other.website
    if keep.confidence is None:
        keep.confidence = other.confidence
    keep.merged += 1 + other.merged


def merge(rows: List[Row]) -> Tuple[List[Row], int]:
    """
    Fold duplicates into one row each. Overture rows come first, so they keep
    their name and position. Grid cells of about 110 m make this near-linear.
    """
    cell = 0.001
    grid: Dict[Tuple[int, int], List[Row]] = {}
    out: List[Row] = []
    merged = 0
    for row in sorted(rows, key=lambda r: (r.overture_id is None, -(r.confidence or 0))):
        cx, cy = int(row.lng // cell), int(row.lat // cell)
        match = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other in grid.get((cx + dx, cy + dy), []):
                    if same_place(other, row) and not (other.overture_id and row.overture_id) and not (other.fsq_id and row.fsq_id):
                        match = other
                        break
                if match:
                    break
            if match:
                break
        if match:
            _fold(match, row)
            merged += 1
        else:
            grid.setdefault((cx, cy), []).append(row)
            out.append(row)
    return out, merged


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------

_COMPARED = ("name", "lat", "lng", "area_id", "categories", "interests", "overture_id", "fsq_id", "confidence", "website")


def upsert(session, city: City, rows: List[Row], release: str, report: Report, today: Optional[date] = None) -> None:
    """Insert or update by source id; count releases a place is missing from; delete at 2 in a row."""
    from app.models.place import Place

    today = today or date.today()
    existing = session.query(Place).filter(Place.city == city.slug).all()
    by_overture = {p.overture_id: p for p in existing if p.overture_id}
    by_fsq = {p.fsq_id: p for p in existing if p.fsq_id}
    seen = set()

    for row in rows:
        place = (row.overture_id and by_overture.get(row.overture_id)) or (row.fsq_id and by_fsq.get(row.fsq_id))
        values = {name: getattr(row, name) for name in _COMPARED}
        if place is None:
            place = Place(city=city.slug, first_seen=today, last_seen=today, last_seen_release=release, missed_releases=0, **values)
            session.add(place)
            report.inserted += 1
        else:
            changed = any(getattr(place, name) != value for name, value in values.items())
            if changed or place.last_seen_release != release or place.missed_releases:
                for name, value in values.items():
                    setattr(place, name, value)
                if place.last_seen_release != release:
                    place.last_seen = today
                place.last_seen_release = release
                place.missed_releases = 0
                place.last_missed_release = None
                report.updated += 1 if changed else 0
                report.unchanged += 0 if changed else 1
            else:
                report.unchanged += 1
        seen.add(id(place))

    for place in existing:
        if id(place) in seen or place.last_missed_release == release:
            continue
        place.missed_releases += 1
        place.last_missed_release = release
        if place.missed_releases >= 2:
            session.delete(place)
            report.deleted += 1
    session.commit()


def table_bytes(session) -> Optional[int]:
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        from sqlalchemy import text

        return session.execute(text("SELECT pg_total_relation_size('places')")).scalar()
    return None


# --------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------

def pinned_release(key: str = "overture_places") -> str:
    sources = yaml.safe_load((REPO_ROOT / "app" / "data" / "sources.yaml").read_text(encoding="utf-8"))["sources"]
    return next(s["release"] for s in sources if s["key"] == key)


def build(city_slug: str, overture: Optional[str], fsq: Optional[str], min_confidence: float, release: str) -> Tuple[List[Row], Report]:
    """Read, filter, merge and give each place its Area. No database writes."""
    city = CITIES[city_slug]
    report = Report(city=city_slug, release=release)
    remote = any(src and "://" in src for src in (overture, fsq))
    con = _connect(remote)
    rows: List[Row] = []
    if overture:
        rows += read_overture(con, overture, city, min_confidence, report)
    if fsq:
        rows += read_fsq(con, fsq, city, report)
    rows, report.merged = merge(rows)
    for row in rows:
        area = area_at(city_slug, row.lat, row.lng)
        row.area_id = area.slug if area else None
    report.kept = len(rows)
    report.in_an_area = sum(1 for r in rows if r.area_id)
    report.per_interest = {key: sum(1 for r in rows if key in r.interests) for key in INTERESTS}
    return rows, report


def run(city_slug: str, overture: Optional[str], fsq: Optional[str], min_confidence: float, release: str, session) -> Report:
    rows, report = build(city_slug, overture, fsq, min_confidence, release)
    upsert(session, CITIES[city_slug], rows, release, report)
    report.table_bytes = table_bytes(session)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build a city's places catalogue from open data.")
    parser.add_argument("--city", required=True, choices=sorted(CITIES))
    parser.add_argument("--release", default=None, help="Overture release; default: the one pinned in app/data/sources.yaml")
    parser.add_argument("--overture", default=None, help="Overture places GeoParquet (path or s3:// glob); default: the pinned release on S3")
    parser.add_argument("--fsq", default=None, help="Foursquare OS Places parquet (path or hf:// glob); skipped when unset")
    parser.add_argument("--report", default=None, help="Write the report as JSON to this file")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from app.core.config import settings
    from app.core.database import SessionLocal

    release = args.release or pinned_release()
    overture = args.overture or OVERTURE_S3.format(release=release)
    if not args.fsq:
        log.warning("No --fsq given: building from Overture only")
    session = SessionLocal()
    try:
        report = run(args.city, overture, args.fsq, settings.CATALOGUE_MIN_CONFIDENCE, release, session)
    finally:
        session.close()
    text = json.dumps(report.to_dict(), indent=2)
    print(text)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
