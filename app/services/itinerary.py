import asyncio
import json
import re
from typing import Dict, Any, List
from openai import AsyncOpenAI
from app.core.cities import City, get_city
from app.core.config import settings
from app.schemas.itinerary import ItineraryGenerate
from app.services.demo_places import demo_slot
from app.services.places import places_service

# Whole words only, so "barbecue" doesn't count as a request for bars.
NIGHTLIFE_RE = re.compile(r"\b(nightlife|bars?|clubs?|clubbing|party|drinks|cocktails?|dancing)\b")

# Demo itinerary: per-person costs in USD by slot and budget, converted to the
# city's currency with its approximate rate.
DEMO_COSTS_USD = {
    "breakfast": {"$": 8, "$$": 15, "$$$": 30},
    "activity": {"$": 0, "$$": 15, "$$$": 30},
    "lunch": {"$": 15, "$$": 30, "$$$": 70},
    "dinner": {"$": 20, "$$": 45, "$$$": 120},
    "nightlife": {"$": 15, "$$": 35, "$$$": 90},
}
DEMO_DAY = [("09:00 AM", "breakfast"), ("11:00 AM", "activity"), ("01:00 PM", "lunch"), ("07:00 PM", "dinner")]
DEMO_NIGHT = ("10:00 PM", "nightlife")
DEMO_COPY = {
    "breakfast": ("Coffee and breakfast", "Start the day at {name}, a favourite in {area}."),
    "activity": ("Explore", "Spend the late morning at {name} in {area}."),
    "lunch": ("Lunch", "Lunch at {name}, one of {area}'s go-to spots."),
    "dinner": ("Dinner", "Settle in for dinner at {name} in {area}."),
    "nightlife": ("Night out", "End the night at {name} in {area}."),
}
# Round demo costs to amounts people would actually quote in each currency.
COST_STEPS = {"JPY": 100, "ZAR": 10}


def wants_nightlife(preferences: str) -> bool:
    return bool(NIGHTLIFE_RE.search((preferences or "").lower()))


def local_cost(usd: float, city: City) -> int:
    step = COST_STEPS.get(city.currency, 1)
    return int(round(usd * city.usd_rate / step) * step)


class ItineraryService:
    def __init__(self):
        # Instantiate OpenAI client if key is set
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL
        self.client = None
        if self.api_key and self.api_key != "your_openai_api_key":
            self.client = AsyncOpenAI(api_key=self.api_key)

    async def generate_itinerary(self, params: ItineraryGenerate) -> Dict[str, Any]:
        """
        Generate a budget-based itinerary using OpenAI (settings.OPENAI_MODEL) grounded in real Google Places candidates.
        """
        city = get_city(params.city)

        # Fall back to the city's demo itinerary if OpenAI is not configured
        if not self.client:
            return self._get_demo_itinerary(params, city)

        categories = ["breakfast", "lunch", "dinner"]
        if wants_nightlife(params.preferences):
            categories.append("nightlife")

        # Fetch candidate places for each day and slot.
        # Days are processed in order so places already used on an earlier day can
        # be excluded from later days (cross-day variety); within a single day the
        # per-category Places lookups run concurrently to cut total latency.
        slots_per_category = 4
        candidates_by_day: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        used_place_ids: set[str] = set()
        for day in range(1, params.duration_days + 1):
            results = await asyncio.gather(
                *(
                    places_service.search_places_for_slot(
                        city,
                        category,
                        params.budget,
                        # Over-fetch so enough candidates survive de-duplication
                        # against both earlier days and earlier slots of this day.
                        max_results=(
                            slots_per_category * (len(categories) + 1)
                            + len(used_place_ids)
                        ),
                    )
                    for category in categories
                ),
                return_exceptions=True,
            )

            day_candidates: Dict[str, List[Dict[str, Any]]] = {}
            # Ids already assigned to an earlier slot on this same day, so a venue
            # is never offered for both e.g. breakfast and lunch.
            day_used_ids: set[str] = set()
            for category, places in zip(categories, results):
                if isinstance(places, Exception):
                    print(f"Error fetching {category} candidates for day {day}: {places}")
                    day_candidates[category] = []
                    continue

                slot: List[Dict[str, Any]] = []
                for p in places or []:
                    place_id = p.get("google_place_id")
                    if place_id and (place_id in used_place_ids or place_id in day_used_ids):
                        continue  # already featured on an earlier day or slot
                    slot.append(
                        {
                            "google_place_id": place_id,
                            "name": p.get("name"),
                            "rating": p.get("rating"),
                            "address": p.get("address"),
                            "price_level": p.get("price_level"),
                            "latitude": p.get("latitude"),
                            "longitude": p.get("longitude"),
                        }
                    )
                    if place_id:
                        day_used_ids.add(place_id)
                    if len(slot) >= slots_per_category:
                        break
                day_candidates[category] = slot

            # Record this day's candidate ids so later days draw from fresh places.
            used_place_ids.update(day_used_ids)
            candidates_by_day[f"day_{day}"] = day_candidates

        candidates_json = json.dumps(candidates_by_day, indent=2)

        prompt = f"""
        Generate a travel itinerary based on the following preferences:
        - Destination: {city.name}
        - Budget Level: {params.budget} (where $ is budget/cheap, $$ is moderate, $$$ is luxury)
        - Duration: {params.duration_days} day(s)
        - Special Preferences/Vibes: {params.preferences or 'None specified'}

        Candidate Places to Choose From (by day and slot):
        {candidates_json}

        The itinerary must be realistic and strictly respect the budget. Estimate a cost per person for each item, as a whole number in {city.currency}.
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
                    "estimated_cost": 25, // whole number, per person, in the currency given in the request
                    "location": "Name of the place or landmark",
                    "google_place_id": "Exact google_place_id from candidate list, or null for general activities"
                }
            ]
        }
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )

            content = response.choices[0].message.content
            itinerary_data = json.loads(content)

            # Build candidate lookup mapping google_place_id -> candidate dict
            candidate_lookup: Dict[str, Dict[str, Any]] = {}
            for day_slots in candidates_by_day.values():
                for slot_places in day_slots.values():
                    for candidate in slot_places:
                        place_id = candidate.get("google_place_id")
                        if place_id:
                            candidate_lookup[place_id] = candidate

            # Validate and enrich items before returning
            itinerary_data["items"] = self._validate_and_enrich_items(
                itinerary_data.get("items", []), candidate_lookup
            )
            # Facts about the request come from the request, not the model.
            itinerary_data.update(
                destination=city.name,
                city=city.slug,
                currency=city.currency,
                budget=params.budget,
                duration_days=params.duration_days,
            )
            return itinerary_data

        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return self._get_demo_itinerary(params, city)

    def _validate_and_enrich_items(
        self,
        items: List[Dict[str, Any]],
        candidate_lookup: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Validate itinerary items against verified candidates and enrich with metadata.
        - If google_place_id is None, leaves item unchanged with verified=False.
        - If google_place_id is present and in candidate_lookup, sets verified=True and adds
          address plus latitude/longitude from the matched candidate.
        - If google_place_id is present but not in candidate_lookup, sets google_place_id=None,
          verified=False, prepends '[Unverified] ' to location, and prints a warning.
        Every item ends up with a boolean verified field.
        """
        validated_items = []
        for item in items:
            enriched_item = dict(item)
            place_id = item.get("google_place_id")

            if place_id is None:
                # Valid generic activity with no place ID
                enriched_item["verified"] = False
            elif place_id in candidate_lookup:
                # Verified candidate place
                matched_candidate = candidate_lookup[place_id]
                enriched_item["verified"] = True
                enriched_item["address"] = matched_candidate.get("address")
                enriched_item["latitude"] = matched_candidate.get("latitude")
                enriched_item["longitude"] = matched_candidate.get("longitude")
            else:
                # Place ID not found in candidate lookup (hallucinated or misused ID)
                print(
                    f"Warning: Invalid place_id '{place_id}' for activity '{item.get('activity')}' "
                    f"not found in candidate places."
                )
                enriched_item["google_place_id"] = None
                enriched_item["verified"] = False
                orig_location = item.get("location") or ""
                enriched_item["location"] = f"[Unverified] {orig_location}"

            validated_items.append(enriched_item)

        return validated_items

    def _get_demo_itinerary(self, params: ItineraryGenerate, city: City) -> Dict[str, Any]:
        """Demo itinerary from the city's demo places, used when OpenAI is not configured."""
        print(f"Using demo data for an itinerary in {city.name}...")

        schedule = list(DEMO_DAY)
        if wants_nightlife(params.preferences):
            schedule.append(DEMO_NIGHT)

        # Rotate through each slot's places so lunch and dinner (and later
        # days) don't repeat a venue while there are others left.
        next_index: Dict[str, int] = {}
        items = []
        for day in range(1, params.duration_days + 1):
            for time, slot in schedule:
                pool = demo_slot(city, slot)
                key = ",".join(sorted({p["category"] for p in pool}))
                index = next_index.get(key, 0)
                next_index[key] = index + 1
                place = pool[index % len(pool)]

                area = place["address"].split(",")[0]
                activity, description = DEMO_COPY[slot]
                items.append({
                    "day": day,
                    "time": time,
                    "activity": activity,
                    "description": description.format(name=place["name"], area=area),
                    "estimated_cost": local_cost(DEMO_COSTS_USD[slot][params.budget], city),
                    "location": place["name"],
                    "address": place["address"],
                    "google_place_id": place["google_place_id"],
                    "category": place["category"],
                    "verified": False,
                })

        days = params.duration_days
        return {
            "title": f"A day out in {city.name}" if days == 1 else f"{days} days in {city.name}",
            "destination": city.name,
            "city": city.slug,
            "currency": city.currency,
            "budget": params.budget,
            "duration_days": days,
            "items": items,
            "demo": True,
        }

itinerary_service = ItineraryService()
