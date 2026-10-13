import re
import time
from typing import Any, Dict, List, Optional

import httpx

from app.core.cities import City
from app.core.config import settings
from app.services.demo_places import demo_search, demo_slot
from app.services.search_intent import detect_intent

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
        self.api_key = settings.GOOGLE_PLACES_API_KEY
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
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.request(
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

        body = {
            "textQuery": f"{query} in {city.name}",
            "locationBias": {
                "circle": {
                    "center": {"latitude": city.lat, "longitude": city.lng},
                    "radius": float(city.radius_m),
                }
            },
            "regionCode": city.country_code,
            "languageCode": "en",
            "pageSize": 20,
        }
        # Keep results to the kind of place asked for: "trendy cafes" returns
        # only cafés, not parks or museums that happen to match the text.
        intent = detect_intent(query)
        if intent and intent.google_type:
            body["includedType"] = intent.google_type
            body["strictTypeFiltering"] = True
        data = await self._request("POST", "places:searchText", field_mask=SEARCH_FIELD_MASK, json=body)

        places = []
        for item in data.get("places", []):
            places.append(parse_place(item))
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

    async def get_photo(self, place_id: str) -> Optional[Dict[str, Optional[str]]]:
        """
        URL and author credit for a place's main photo, or None when there is
        no photo (or no API key). Results are cached for an hour.
        """
        if not self.live or place_id.startswith("mock_") or not PLACE_ID_RE.match(place_id):
            return None

        cached = self._photo_urls.get(place_id)
        if cached and cached[0] > time.monotonic():
            return cached[1]

        photo = self._photo_refs.get(place_id)
        if photo is None:
            details = await self._request("GET", f"places/{place_id}", field_mask="photos")
            photos = details.get("photos") or []
            photo = photos[0] if photos else None

        result = None
        if photo and photo.get("name"):
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


places_service = GooglePlacesService()
