import json
from typing import Dict, Any, List, Optional
from openai import OpenAI
from app.core.config import settings
from app.schemas.itinerary import ItineraryGenerate
from app.services.places import places_service

class ItineraryService:
    def __init__(self):
        # Instantiate OpenAI client if key is set
        self.api_key = settings.OPENAI_API_KEY
        self.client = None
        if self.api_key and self.api_key != "your_openai_api_key":
            self.client = OpenAI(api_key=self.api_key)

    async def generate_itinerary(self, params: ItineraryGenerate) -> Dict[str, Any]:
        """
        Generate a budget-based itinerary using OpenAI GPT-4o-mini grounded in real Google Places candidates.
        """
        # Fallback to mock generation if OpenAI client is not initialized
        if not self.client:
            return self._get_mock_itinerary(params)

        # Check preferences for nightlife/bars/clubs keywords
        pref_lower = (params.preferences or "").lower()
        include_nightlife = any(kw in pref_lower for kw in ["nightlife", "bar", "club", "party"])

        categories = ["breakfast", "lunch", "dinner"]
        if include_nightlife:
            categories.append("nightlife")

        # Fetch candidate places for each day and slot
        candidates_by_day: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for day in range(1, params.duration_days + 1):
            day_candidates: Dict[str, List[Dict[str, Any]]] = {}
            for category in categories:
                try:
                    places = await places_service.search_places_for_slot(
                        params.destination, category, params.budget, max_results=4
                    )
                    day_candidates[category] = [
                        {
                            "google_place_id": p.get("google_place_id"),
                            "name": p.get("name"),
                            "rating": p.get("rating"),
                            "address": p.get("address"),
                            "price_level": p.get("price_level")
                        }
                        for p in (places or [])
                    ]
                except Exception as e:
                    print(f"Error fetching {category} candidates for day {day}: {e}")
                    day_candidates[category] = []
            candidates_by_day[f"day_{day}"] = day_candidates

        candidates_json = json.dumps(candidates_by_day, indent=2)

        prompt = f"""
        Generate a travel itinerary based on the following preferences:
        - Destination: {params.destination}
        - Budget Level: {params.budget} (where $ is budget/cheap, $$ is moderate, $$$ is luxury)
        - Duration: {params.duration_days} day(s)
        - Special Preferences/Vibes: {params.preferences or 'None specified'}

        Candidate Places to Choose From (by day and slot):
        {candidates_json}

        The itinerary must be realistic and strictly respect the budget. Specify reasonable estimated costs in USD for each item.
        """

        system_instruction = """
        You are an expert travel planner. You generate highly engaging, customized, and budget-appropriate itineraries.

        GROUNDING RULES FOR PLACES AND ACTIVITIES:
        - You are provided with a verified candidate list of real places organized by day and time slot.
        - For venue-based activities, you must ONLY select places from the provided candidate list for each slot.
        - When choosing a place from the candidate list, you MUST use the exact google_place_id provided (never invented, never null).
        - If you want to add a non-place activity with no candidate (e.g. "walk along the river", "stroll along the beach"), you should set google_place_id to null ONLY in that specific case and clearly indicate location as a general area rather than a specific business.
        - If a slot has an empty candidate list, you may suggest a generic activity with google_place_id set to null.

        You must return your response as a JSON object matching this schema:
        {
            "title": "A fun and catchy title for the itinerary",
            "destination": "The destination city/location",
            "budget": "The budget tier matching the input ($, $$, or $$$)",
            "duration_days": 1, // integer matching the input duration
            "items": [
                {
                    "day": 1, // integer day number
                    "time": "e.g., 09:00 AM",
                    "activity": "Name of the activity or place",
                    "description": "Short, engaging description of what to do there, matching the requested vibe.",
                    "estimated_cost": 25, // integer estimation in USD
                    "location": "Name of the place or landmark",
                    "google_place_id": "Exact google_place_id from candidate list, or null for general activities"
                }
            ]
        }
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            itinerary_data = json.loads(content)
            return itinerary_data

        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return self._get_mock_itinerary(params)

    def _get_mock_itinerary(self, params: ItineraryGenerate) -> Dict[str, Any]:
        """Fallback mock itinerary generator when OpenAI key is missing."""
        print("Using mock data for Itinerary generation...")
        
        # Build items list based on duration days
        items = []
        activities_pool = {
            "$": [
                {"activity": "Morning Jog & Local Coffee", "location": "Organic Garden Bowls", "description": "Grab a cheap smoothie and jog along the beach or park.", "cost": 8},
                {"activity": "Explore Free Public Parks/Beaches", "location": "Crandon Park Beach", "description": "Soak up the sun, swim, or read a book by the water.", "cost": 0},
                {"activity": "Food Truck Lunch Caravan", "location": "Wynwood Food Truck Rally", "description": "Grab delicious tacos or empanadas from local street vendors.", "cost": 12},
                {"activity": "Self-Guided Street Art Tour", "location": "Wynwood Arts District", "description": "Walk around and take photos of the world-famous murals.", "cost": 0},
                {"activity": "Chill Sunset Picnic", "location": "South Pointe Park", "description": "Bring some grocery snacks and enjoy the ocean breeze as the sun sets.", "cost": 10},
                {"activity": "Live Jazz night (No cover)", "location": "Lagniappe", "description": "Sip a draft beer and listen to local bands in a backyard setting.", "cost": 15}
            ],
            "$$": [
                {"activity": "Aesthetic Brunch", "location": "The Block Cafe & Bistro", "description": "Enjoy artisanal avocado toast and premium pour-over coffee.", "cost": 22},
                {"activity": "Museum Tour", "location": "Pérez Art Museum Miami (PAMM)", "description": "Explore modern and contemporary international art.", "cost": 18},
                {"activity": "Waterfront Lunch", "location": "The Rusty Pelican", "description": "Eat fresh seafood with a beautiful view of the skyline.", "cost": 35},
                {"activity": "Kayaking/Paddleboarding", "location": "Key Biscayne Kayaks", "description": "Rent a board and explore the calm bay waters.", "cost": 25},
                {"activity": "Trendy Dinner & Drinks", "location": "Wynwood Art Tavern", "description": "Indulge in fusion tapas and handcrafted cocktails.", "cost": 45},
                {"activity": "Rooftop Lounge Hangout", "location": "Sunset Lounge Rooftop", "description": "Have drinks with a panoramic view of the neon lit city.", "cost": 30}
            ],
            "$$$": [
                {"activity": "VIP Sunrise Spa Session", "location": "The Standard Spa", "description": "Treat yourself to hydrotherapy and a massage.", "cost": 150},
                {"activity": "Private Yacht/Boat Charter", "location": "Miami Yacht Charters", "description": "Private cruise around Biscayne Bay with champagne.", "cost": 250},
                {"activity": "Fine Dining Omakase Lunch", "location": "Hiden Miami", "description": "Exquisite multi-course chef's choice sushi selection.", "cost": 120},
                {"activity": "High-End Designer Shopping", "location": "Design District", "description": "Browse luxury boutiques and high-fashion flagships.", "cost": 0},
                {"activity": "Michelin Star Dinner", "location": "L'Atelier de Joël Robuchon", "description": "Exceptional tasting menu from award-winning chefs.", "cost": 200},
                {"activity": "Elite VIP Club Experience", "location": "LIV Nightclub", "description": "Premium table service and dancing to world-class DJs.", "cost": 180}
            ]
        }

        # Select pool based on budget
        pool = activities_pool.get(params.budget, activities_pool["$$"])
        
        # Generate items for each day
        day_sequence = ["Morning", "Afternoon", "Evening"]
        for d in range(1, params.duration_days + 1):
            for i, period in enumerate(day_sequence):
                act_idx = ((d - 1) * 3 + i) % len(pool)
                act = pool[act_idx]
                items.append({
                    "day": d,
                    "time": "09:00 AM" if period == "Morning" else ("01:00 PM" if period == "Afternoon" else "07:00 PM"),
                    "activity": act["activity"],
                    "description": act["description"],
                    "estimated_cost": act["cost"],
                    "location": act["location"],
                    "google_place_id": f"mock_place_{act_idx + 1}"
                })

        title_pref = f" ({params.preferences})" if params.preferences else ""
        return {
            "title": f"Ultimate {params.budget} Vibe in {params.destination}{title_pref}",
            "destination": params.destination,
            "budget": params.budget,
            "duration_days": params.duration_days,
            "items": items
        }

itinerary_service = ItineraryService()
