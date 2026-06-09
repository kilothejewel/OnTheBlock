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

places_service = GooglePlacesService()
