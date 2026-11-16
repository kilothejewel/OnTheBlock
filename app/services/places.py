import re
import time
from typing import Any, Dict, List, Optional

import httpx

from app.core.cities import City
from app.core.config import settings
from app.core.http_client import get_http_client
from app.core.observability import count_call
from app.services.demo_places import demo_search, demo_slot

PLACES_API = "https://places.googleapis.com/v1"

# Only the fields we show. The field mask also decides which tier a call is billed at.
SEARCH_FIELD_MASK = ",".join(
    f"places.{field}"
    for field in (
        "id",
        "displayName",
        "formattedAddress",
        "location",
        "rating",
        "userRatingCount",
        "priceLevel",
        "types",
        "photos",
    )
)

# Display details for saved Plans and places (#29): Place Details **Pro** SKU
# fields only (5,000 free a month). Rating, hours and price are Enterprise,
# kept for the live check of final Stops (#93). A test fails on any other field.
DETAILS_PRO_FIELDS = ("id", "displayName", "formattedAddress", "location", "types", "googleMapsUri")
DETAILS_FIELD_MASK = ",".join(DETAILS_PRO_FIELDS)
MAX_DETAILS_IDS = 20

# Places API (New) returns price level as an enum; the app uses 0-4.
PRICE_LEVELS = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}

# Budget tier -> acceptable price levels. Places with no price level are kept.
BUDGET_PRICE_RANGES = {"$": (0, 1), "$$": (1, 2), "$$$": (2, 4)}

# Place ids are URL-safe tokens; checking them keeps request paths well-formed.
PLACE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,300}$")
PHOTO_TTL_SECONDS = 60 * 60
CACHE_LIMIT = 2000


class PlacesError(Exception):
    """A Google Places request failed."""


def parse_place(item: Dict[str, Any]) -> Dict[str, Any]:
    """Map a Places API (New) place to the app's place shape."""
    location = item.get("location") or {}
    return {
        "google_place_id": item.get("id"),
        "name": (item.get("displayName") or {}).get("text"),
        "rating": item.get("rating"),
        "user_rating_count": item.get("userRatingCount"),
        "address": item.get("formattedAddress"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "price_level": PRICE_LEVELS.get(item.get("priceLevel")),
        "types": ", ".join(item.get("types", [])),
    }


class GooglePlacesService:
    def __init__(self):
        # Search, display details and photos use the otb-display project's key;
        # the live check of final Stops (#93) uses otb-live's (#44).
        self.api_key = settings.GOOGLE_DISPLAY_KEY or settings.GOOGLE_PLACES_API_KEY
        self.live_key = settings.GOOGLE_LIVE_KEY or settings.GOOGLE_PLACES_API_KEY
        # place id -> first photo reference seen in a search, so showing a
        # result's photo needs no extra details call
        self._photo_refs: Dict[str, Dict[str, Any]] = {}
        # place id -> (expires at, photo url + credit)
        self._photo_urls: Dict[str, tuple] = {}

    @property
    def live(self) -> bool:
        """False without a real API key; the service then serves demo data."""
        return bool(self.api_key) and self.api_key != "your_google_places_api_key"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        field_mask: Optional[str] = None,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        headers = {"X-Goog-Api-Key": self.api_key}
        if field_mask:
            headers["X-Goog-FieldMask"] = field_mask
        count_call("google")
        try:
            response = await get_http_client().request(
                method, f"{PLACES_API}/{path}", headers=headers, json=json, params=params
            )
        except httpx.HTTPError as exc:
            raise PlacesError(f"Google Places request failed: {exc}") from exc
        if response.status_code != 200:
            raise PlacesError(f"Google Places returned {response.status_code}: {response.text[:200]}")
        return response.json()

    async def search_places(self, query: str, city: City) -> List[Dict[str, Any]]:
        """
        Search places in a city with Places API (New) Text Search, biased to the
        city's area. Raises PlacesError if Google can't be reached or refuses.
        """
        if not self.live:
            return demo_search(city, query)

        (south, west), (north, east) = city.bounds
        body = {
            "textQuery": f"{query} in {city.name}",
            # Only places inside the city's metro extent (app/data/cities.yaml).
            "locationRestriction": {
                "rectangle": {
                    "low": {"latitude": south, "longitude": west},
                    "high": {"latitude": north, "longitude": east},
                }
            },
            "regionCode": city.country_code,
            "languageCode": "en",
            "pageSize": 20,
        }
        data = await self._request("POST", "places:searchText", field_mask=SEARCH_FIELD_MASK, json=body)

        places = []
        for item in data.get("places", []):
            place = parse_place(item)
            lat, lng = place["latitude"], place["longitude"]
            if lat is not None and lng is not None and not city.contains(lat, lng):
                continue  # an edge case Google can return just outside the rectangle
            places.append(place)
            photos = item.get("photos") or []
            if item.get("id") and photos:
                self._remember(self._photo_refs, item["id"], photos[0])
        return places

    async def search_places_for_slot(
        self, city: City, category: str, budget: str, max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Candidates for one itinerary slot (e.g. "breakfast", "nightlife") in a
        city, filtered to the budget tier and sorted by rating (unrated last).
        """
        if not self.live:
            return demo_slot(city, category)[:max_results]

        places = await self.search_places(f"best {category} spots", city)
        min_price, max_price = BUDGET_PRICE_RANGES.get(budget, (0, 4))
        in_budget = [
            p for p in places
            if p["price_level"] is None or min_price <= p["price_level"] <= max_price
        ]
        in_budget.sort(
            key=lambda p: (p["rating"] is not None, p["rating"] or 0),
            reverse=True,
        )
        return in_budget[:max_results]

    async def get_details(self, place_ids: List[str], db=None, pool: str = "users") -> List[Dict[str, Any]]:
        """
        Display details for up to 20 place IDs, in the order given, duplicates
        once. Demo IDs get Demo data (labelled); without a key, or when the
        quota guard refuses (#121), a place gets our catalogue's name and Area
        with details_available false, and Google isn't called. Nothing is
        cached: only place IDs may be stored (Google terms).
        """
        from app.services.quota import quota

        unique = list(dict.fromkeys(place_ids))
        results: Dict[str, Dict[str, Any]] = {}
        for place_id in unique:
            if place_id.startswith("mock_"):
                results[place_id] = _demo_details(place_id)
                continue
            if not self.live or not PLACE_ID_RE.match(place_id) or not quota.take("google.details_pro", pool=pool):
                results[place_id] = _catalogue_details(db, place_id)
                continue
            try:
                data = await self._request("GET", f"places/{place_id}", field_mask=DETAILS_FIELD_MASK)
            except PlacesError:
                results[place_id] = _catalogue_details(db, place_id)
                continue
            location = data.get("location") or {}
            results[place_id] = {
                "google_place_id": place_id,
                "name": (data.get("displayName") or {}).get("text"),
                "address": data.get("formattedAddress"),
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
                "types": data.get("types") or [],
                "maps_url": data.get("googleMapsUri"),
                "area": None,
                "source": "google",
                "details_available": True,
            }
        return [results[place_id] for place_id in unique]

    async def get_photo(self, place_id: str, pool: str = "users") -> Optional[Dict[str, Optional[str]]]:
        """
        URL and author credit for a place's main photo, or None when there is
        no photo (or no API key). Results are cached for an hour.
        """
        if not self.live or place_id.startswith("mock_") or not PLACE_ID_RE.match(place_id):
            return None

        cached = self._photo_urls.get(place_id)
        if cached and cached[0] > time.monotonic():
            return cached[1]

        from app.services.quota import quota

        photo = self._photo_refs.get(place_id)
        if photo is None:
            if not quota.take("google.details_pro", pool=pool):
                return None
            details = await self._request("GET", f"places/{place_id}", field_mask="photos")
            photos = details.get("photos") or []
            photo = photos[0] if photos else None

        result = None
        if photo and photo.get("name"):
            if not quota.take("google.photos", pool=pool):
                return None
            media = await self._request(
                "GET",
                f"{photo['name']}/media",
                params={"maxWidthPx": 800, "skipHttpRedirect": "true"},
            )
            author = (photo.get("authorAttributions") or [{}])[0]
            result = {
                "url": media.get("photoUri"),
                "attribution": author.get("displayName"),
                "attribution_url": author.get("uri"),
            }

        self._remember(self._photo_urls, place_id, (time.monotonic() + PHOTO_TTL_SECONDS, result))
        return result

    @staticmethod
    def _remember(cache: Dict[str, Any], key: str, value: Any) -> None:
        """Store in a size-capped cache, dropping the oldest entry when full."""
        if key not in cache and len(cache) >= CACHE_LIMIT:
            cache.pop(next(iter(cache)))
        cache[key] = value


def _demo_details(place_id: str) -> Dict[str, Any]:
    """A Demo place's details (mock_<city>_<n>), always labelled as Demo data."""
    from app.core.cities import CITIES
    from app.services.demo_places import demo_places

    match = re.fullmatch(r"mock_(.+)_(\d+)", place_id)
    city = CITIES.get(match.group(1)) if match else None
    place = next((p for p in demo_places(city) if p["google_place_id"] == place_id), None) if city else None
    return {
        "google_place_id": place_id, "name": place["name"] if place else None,
        "address": place["address"] if place else None, "latitude": None, "longitude": None,
        "types": [t.strip() for t in place["types"].split(",")] if place else [], "maps_url": None,
        "area": None, "source": "demo", "details_available": place is not None,
    }


def _catalogue_details(db, place_id: str) -> Dict[str, Any]:
    """What our own catalogue knows about a Google place ID: its name and Area, never Google's fields."""
    from app.models.place import Place

    found = None
    if db is not None:
        try:
            row = db.query(Place).filter(Place.google_place_id == place_id).first()
            found = (row.name, row.area_id, row.lat, row.lng) if row else None
        except Exception:  # the catalogue is a fallback; an outage means "unknown"
            db.rollback()
    name, area, lat, lng = found or (None, None, None, None)
    return {
        "google_place_id": place_id, "name": name, "address": None, "latitude": lat, "longitude": lng,
        "types": [], "maps_url": None, "area": area, "source": "catalogue" if found else "unknown",
        "details_available": False,
    }


places_service = GooglePlacesService()
