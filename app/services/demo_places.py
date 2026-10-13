"""
Demo data used when no Google Places API key is configured.

Real, well-known places in each supported city, so a demo looks right for the
city it is showing. Addresses are neighbourhood-level and ratings are left out
on purpose: we don't publish made-up scores for real businesses. Every id
starts with "mock_" so the app can label the data as a demo.
"""

from typing import Any, Dict, List

from app.core.cities import City
from app.services.search_intent import detect_intent, search_words

# (name, neighbourhood, category, price level 0-4 or None, Google-style types)
DEMO_PLACES: Dict[str, List[tuple]] = {
    "miami": [
        ("Panther Coffee", "Wynwood", "cafe", 1, "cafe, coffee_shop"),
        ("Zak the Baker", "Wynwood", "cafe", 1, "bakery, cafe"),
        ("Coyo Taco", "Wynwood", "food", 1, "mexican_restaurant, restaurant"),
        ("Versailles Restaurant", "Little Havana", "food", 2, "cuban_restaurant, restaurant"),
        ("Joe's Stone Crab", "South Beach", "food", 3, "seafood_restaurant, restaurant"),
        ("Pérez Art Museum Miami", "Downtown", "art", None, "art_museum, museum"),
        ("Wynwood Walls", "Wynwood", "art", None, "art_gallery, tourist_attraction"),
        ("South Pointe Park", "South Beach", "outdoor", None, "park"),
        ("Ball & Chain", "Little Havana", "nightlife", 2, "bar, live_music_venue"),
        ("Club Space", "Downtown", "nightlife", 3, "night_club"),
    ],
    "london": [
        ("Monmouth Coffee Company", "Borough", "cafe", 1, "cafe, coffee_shop"),
        ("E5 Bakehouse", "Hackney", "cafe", 1, "bakery, cafe"),
        ("Borough Market", "Southwark", "food", 1, "market, food"),
        ("Dishoom Shoreditch", "Shoreditch", "food", 2, "indian_restaurant, restaurant"),
        ("The Ledbury", "Notting Hill", "food", 4, "fine_dining_restaurant, restaurant"),
        ("Tate Modern", "Bankside", "art", None, "art_museum, museum"),
        ("Victoria and Albert Museum", "South Kensington", "art", None, "museum"),
        ("Primrose Hill", "Camden", "outdoor", None, "park"),
        ("Ronnie Scott's", "Soho", "nightlife", 3, "bar, live_music_venue"),
        ("Fabric", "Farringdon", "nightlife", 2, "night_club"),
    ],
    "cape-town": [
        ("Truth Coffee Roasting", "City Bowl", "cafe", 2, "cafe, coffee_shop"),
        ("Jason Bakery", "Bree Street", "cafe", 1, "bakery, cafe"),
        ("Mzoli's Place", "Gugulethu", "food", 1, "barbecue_restaurant, restaurant"),
        ("Kloof Street House", "Gardens", "food", 2, "restaurant"),
        ("La Colombe", "Constantia", "food", 4, "fine_dining_restaurant, restaurant"),
        ("Zeitz MOCAA", "V&A Waterfront", "art", None, "art_museum, museum"),
        ("Kirstenbosch National Botanical Garden", "Newlands", "outdoor", None, "botanical_garden, park"),
        ("Bo-Kaap", "Bo-Kaap", "outdoor", None, "neighbourhood, tourist_attraction"),
        ("The Gin Bar", "City Bowl", "nightlife", 2, "bar, cocktail_bar"),
        ("Tjing Tjing Rooftop Bar", "City Bowl", "nightlife", 2, "bar, rooftop"),
    ],
    "johannesburg": [
        ("Father Coffee", "Braamfontein", "cafe", 1, "cafe, coffee_shop"),
        ("Bean There Coffee Company", "Milpark", "cafe", 1, "cafe, coffee_shop"),
        ("Neighbourgoods Market", "Braamfontein", "food", 1, "market, food"),
        ("Sakhumzi Restaurant", "Soweto", "food", 2, "south_african_restaurant, restaurant"),
        ("Marble", "Rosebank", "food", 3, "steak_house, restaurant"),
        ("Apartheid Museum", "Ormonde", "art", None, "history_museum, museum"),
        ("Arts on Main", "Maboneng", "art", None, "art_gallery, tourist_attraction"),
        ("Zoo Lake", "Parkview", "outdoor", None, "park"),
        ("Kitchener's Carvery Bar", "Braamfontein", "nightlife", 1, "bar, live_music_venue"),
        ("The Great Dane", "Melville", "nightlife", 1, "bar, night_club"),
    ],
    "tokyo": [
        ("Blue Bottle Coffee Kiyosumi-Shirakawa", "Kiyosumi", "cafe", 2, "cafe, coffee_shop"),
        ("Fuglen Tokyo", "Tomigaya", "cafe", 2, "cafe, cocktail_bar"),
        ("Ichiran Shibuya", "Shibuya", "food", 1, "ramen_restaurant, restaurant"),
        ("Tsukiji Outer Market", "Tsukiji", "food", 1, "market, food"),
        ("Gonpachi Nishi-Azabu", "Nishi-Azabu", "food", 2, "japanese_restaurant, restaurant"),
        ("teamLab Planets", "Toyosu", "art", None, "art_museum, tourist_attraction"),
        ("Mori Art Museum", "Roppongi", "art", None, "art_museum, museum"),
        ("Yoyogi Park", "Shibuya", "outdoor", None, "park"),
        ("Golden Gai", "Shinjuku", "nightlife", 1, "bar"),
        ("Womb", "Shibuya", "nightlife", 3, "night_club"),
    ],
}

# Itinerary slot -> demo categories that can fill it
SLOT_CATEGORIES = {
    "breakfast": ["cafe"],
    "lunch": ["food"],
    "dinner": ["food"],
    "activity": ["art", "outdoor"],
    "nightlife": ["nightlife"],
}


def demo_places(city: City) -> List[Dict[str, Any]]:
    """The city's demo places, shaped like Places API results."""
    places = []
    for i, (name, area, category, price_level, types) in enumerate(DEMO_PLACES[city.slug], start=1):
        places.append(
            {
                "google_place_id": f"mock_{city.slug}_{i}",
                "name": name,
                "rating": None,
                "user_rating_count": None,
                "address": f"{area}, {city.name}",
                "latitude": None,
                "longitude": None,
                "price_level": price_level,
                "types": types,
                "category": category,
            }
        )
    return places


def demo_search(city: City, query: str) -> List[Dict[str, Any]]:
    """
    The city's demo places that fit the query: the kind of place it asks for
    ("cafes", "rooftop bars"), or a name or type it mentions. No match means
    no results, rather than unrelated places.
    """
    intent = detect_intent(query)
    words = search_words(query)

    def matches(place: Dict[str, Any]) -> bool:
        if intent and place["category"] == intent.category:
            return True
        # Whole words only, so "bars" doesn't match "barbecue_restaurant".
        tokens = set(search_words(f"{place['name']} {place['types'].replace('_', ' ')}"))
        return any(w in tokens or w.rstrip("s") in tokens for w in words)

    return [p for p in demo_places(city) if matches(p)]


def demo_slot(city: City, slot: str) -> List[Dict[str, Any]]:
    """Demo places that fit an itinerary slot such as 'breakfast' or 'nightlife'."""
    categories = SLOT_CATEGORIES.get(slot, ["food"])
    return [p for p in demo_places(city) if p["category"] in categories]
