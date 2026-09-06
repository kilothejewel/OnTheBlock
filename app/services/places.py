import httpx
from typing import List, Dict, Any, Optional
from app.core.config import settings

class GooglePlacesService:
    def __init__(self):
        self.api_key = settings.GOOGLE_PLACES_API_KEY
        self.base_url = "https://maps.googleapis.com/maps/api/place"

    async def search_places(self, query: str, location: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for places using Google Places Text Search.
        Example query: 'restaurants in Miami' or 'trendy spots in Soho, London'
        """
        # If API key is empty or not set, use mock fallback to prevent crash and show visual data
        if not self.api_key or self.api_key == "your_google_places_api_key":
            return self._get_mock_places(query)

        url = f"{self.base_url}/textsearch/json"
        params = {
            "query": query,
            "key": self.api_key
        }
        if location:
            params["location"] = location

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])
                
                places = []
                for item in results:
                    places.append({
                        "google_place_id": item.get("place_id"),
                        "name": item.get("name"),
                        "rating": item.get("rating"),
                        "address": item.get("formatted_address"),
                        "latitude": item.get("geometry", {}).get("location", {}).get("lat"),
                        "longitude": item.get("geometry", {}).get("location", {}).get("lng"),
                        "price_level": item.get("price_level"),
                        "types": ", ".join(item.get("types", []))
                    })
                return places
            except Exception as e:
                print(f"Error calling Google Places API: {e}")
                return self._get_mock_places(query)

    async def get_place_details(self, place_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific place.
        """
        if not self.api_key or self.api_key == "your_google_places_api_key":
            return self._get_mock_place_details(place_id)

        url = f"{self.base_url}/details/json"
        params = {
            "place_id": place_id,
            "key": self.api_key
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                result = data.get("result", {})
                
                return {
                    "google_place_id": place_id,
                    "name": result.get("name"),
                    "rating": result.get("rating"),
                    "address": result.get("formatted_address"),
                    "latitude": result.get("geometry", {}).get("location", {}).get("lat"),
                    "longitude": result.get("geometry", {}).get("location", {}).get("lng"),
                    "price_level": result.get("price_level"),
                    "types": ", ".join(result.get("types", []))
                }
            except Exception as e:
                print(f"Error calling Google Places Details API: {e}")
                return self._get_mock_place_details(place_id)

    async def search_places_for_slot(
        self,
        destination: str,
        category: str,
        budget: str,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for places for a specific itinerary slot based on destination,
        category, and budget tier.

        Parameters:
            destination: The target city or location (e.g. "Tokyo", "Paris").
            category: Activity category (e.g. "breakfast", "lunch", "dinner", "nightlife", "activity", "coffee").
            budget: Price tier ("$", "$$", or "$$$").
            max_results: Maximum number of places to return (default 5).

        Returns:
            List of place dictionaries filtered by budget and sorted by rating descending (nulls last).
        """
        # Budget to Google Places price_level range mapping:
        # "$" -> 0-1, "$$" -> 1-2, "$$$" -> 2-4
        budget_price_ranges = {
            "$": (0, 1),
            "$$": (1, 2),
            "$$$": (2, 4),
        }
        min_price, max_price = budget_price_ranges.get(budget, (0, 4))

        # If API key is empty or not set, use mock fallback
        if not self.api_key or self.api_key == "your_google_places_api_key":
            return self._get_mock_places_for_slot(destination, category, budget)[:max_results]

        query = f"best {category} spots in {destination}"
        url = f"{self.base_url}/textsearch/json"
        params = {
            "query": query,
            "key": self.api_key
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])

                places = []
                for item in results:
                    places.append({
                        "google_place_id": item.get("place_id"),
                        "name": item.get("name"),
                        "rating": item.get("rating"),
                        "address": item.get("formatted_address"),
                        "latitude": item.get("geometry", {}).get("location", {}).get("lat"),
                        "longitude": item.get("geometry", {}).get("location", {}).get("lng"),
                        "price_level": item.get("price_level"),
                        "types": ", ".join(item.get("types", []))
                    })

                # Filter by price_level: keep places where price_level falls within range or is missing/null
                filtered_places = [
                    p for p in places
                    if p.get("price_level") is None or (min_price <= p.get("price_level") <= max_price)
                ]

                # Sort by rating descending (nulls last)
                sorted_places = sorted(
                    filtered_places,
                    key=lambda p: (
                        p.get("rating") is not None,
                        p.get("rating") if p.get("rating") is not None else float("-inf")
                    ),
                    reverse=True
                )

                return sorted_places[:max_results]
            except Exception as e:
                print(f"Error calling Google Places API: {e}")
                return self._get_mock_places_for_slot(destination, category, budget)[:max_results]

    def _get_mock_places(self, query: str) -> List[Dict[str, Any]]:
        """Mock data fallback if API key is not configured."""
        print("Using mock data for Google Places search...")
        return [
            {
                "google_place_id": "mock_place_1",
                "name": "The Block Cafe & Bistro",
                "rating": 4.7,
                "address": "123 Main St, Miami, FL",
                "latitude": 25.7617,
                "longitude": -80.1918,
                "price_level": 2,
                "types": "cafe, restaurant, food"
            },
            {
                "google_place_id": "mock_place_2",
                "name": "Sunset Lounge Rooftop",
                "rating": 4.5,
                "address": "456 Ocean Dr, Miami, FL",
                "latitude": 25.7781,
                "longitude": -80.1313,
                "price_level": 3,
                "types": "bar, night_club, point_of_interest"
            },
            {
                "google_place_id": "mock_place_3",
                "name": "Wynwood Art Tavern",
                "rating": 4.6,
                "address": "789 NW 2nd Ave, Miami, FL",
                "latitude": 25.8015,
                "longitude": -80.1991,
                "price_level": 2,
                "types": "bar, restaurant, establishment"
            },
            {
                "google_place_id": "mock_place_4",
                "name": "Blue Velvet Jazz Lounge",
                "rating": 4.8,
                "address": "101 Brickell Ave, Miami, FL",
                "latitude": 25.7650,
                "longitude": -80.1905,
                "price_level": 3,
                "types": "bar, restaurant, food"
            },
            {
                "google_place_id": "mock_place_5",
                "name": "Organic Garden Bowls",
                "rating": 4.4,
                "address": "202 Coral Way, Miami, FL",
                "latitude": 25.7505,
                "longitude": -80.2110,
                "price_level": 1,
                "types": "restaurant, health, food"
            }
        ]

    def _get_mock_place_details(self, place_id: str) -> Dict[str, Any]:
        """Mock data fallback for place details."""
        name_map = {
            "mock_place_1": "The Block Cafe & Bistro",
            "mock_place_2": "Sunset Lounge Rooftop",
            "mock_place_3": "Wynwood Art Tavern",
            "mock_place_4": "Blue Velvet Jazz Lounge",
            "mock_place_5": "Organic Garden Bowls"
        }
        address_map = {
            "mock_place_1": "123 Main St, Miami, FL",
            "mock_place_2": "456 Ocean Dr, Miami, FL",
            "mock_place_3": "789 NW 2nd Ave, Miami, FL",
            "mock_place_4": "101 Brickell Ave, Miami, FL",
            "mock_place_5": "202 Coral Way, Miami, FL"
        }
        return {
            "google_place_id": place_id,
            "name": name_map.get(place_id, f"Premium Spot {place_id.split('_')[-1]}"),
            "rating": 4.6,
            "address": address_map.get(place_id, "999 Luxe Blvd, Miami, FL"),
            "latitude": 25.7617,
            "longitude": -80.1918,
            "price_level": 2,
            "types": "restaurant, food, point_of_interest"
        }

    def _get_mock_places_for_slot(self, destination: str, category: str, budget: str) -> List[Dict[str, Any]]:
        """
        Mock data fallback for slot searches if API key is not configured.
        Returns 3 plausible mock places matching the requested category and budget.
        """
        print("Using mock data for Google Places slot search...")
        cat_title = category.title()
        cat_slug = category.lower().replace(" ", "_")

        price_level_map = {
            "$": 1,
            "$$": 2,
            "$$$": 3,
        }
        price_level = price_level_map.get(budget, 2)

        # Placeholder coordinates for mock/no-API-key mode only; not reflective of the actual destination.
        return [
            {
                "google_place_id": f"mock_{cat_slug}_1",
                "name": f"{cat_title} Spot 1",
                "rating": 4.8,
                "address": f"101 Main St, {destination}",
                "latitude": 40.7128,
                "longitude": -74.0060,
                "price_level": price_level,
                "types": f"{category.lower()}, point_of_interest, establishment"
            },
            {
                "google_place_id": f"mock_{cat_slug}_2",
                "name": f"{cat_title} Spot 2",
                "rating": 4.6,
                "address": f"202 Market St, {destination}",
                "latitude": 40.7145,
                "longitude": -74.0042,
                "price_level": price_level,
                "types": f"{category.lower()}, point_of_interest, establishment"
            },
            {
                "google_place_id": f"mock_{cat_slug}_3",
                "name": f"{cat_title} Spot 3",
                "rating": 4.5,
                "address": f"303 Grand Ave, {destination}",
                "latitude": 40.7112,
                "longitude": -74.0083,
                "price_level": price_level,
                "types": f"{category.lower()}, point_of_interest, establishment"
            }
        ]

places_service = GooglePlacesService()
