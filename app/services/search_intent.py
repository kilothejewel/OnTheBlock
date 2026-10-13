"""
Work out what kind of place a search asks for, so results stay on topic:
"trendy cafes" should return cafés, not a botanical garden.
"""

import re
from dataclasses import dataclass
from typing import Optional

# word -> (app category, Google Places type to filter on, or None)
# A Google type is only set where it can't exclude good results: "brunch" spots
# are often restaurants, so brunch narrows the category but not the Google type.
SEARCH_TERMS = {
    **dict.fromkeys(["cafe", "cafes", "café", "cafés", "coffee", "espresso"], ("cafe", "cafe")),
    **dict.fromkeys(["bakery", "bakeries"], ("cafe", "bakery")),
    **dict.fromkeys(["brunch", "breakfast", "tea"], ("cafe", None)),
    **dict.fromkeys(["bar", "bars", "pub", "pubs"], ("nightlife", "bar")),
    **dict.fromkeys(["club", "clubs", "nightclub", "nightclubs"], ("nightlife", "night_club")),
    **dict.fromkeys(["nightlife", "cocktail", "cocktails", "drinks", "wine", "rooftop", "rooftops", "jazz", "lounge"], ("nightlife", None)),
    **dict.fromkeys(["restaurant", "restaurants"], ("food", "restaurant")),
    **dict.fromkeys(["food", "eat", "eats", "lunch", "dinner", "sushi", "ramen", "pizza", "tacos", "burger", "burgers", "seafood", "steak", "market", "markets"], ("food", None)),
    **dict.fromkeys(["museum", "museums"], ("art", "museum")),
    **dict.fromkeys(["gallery", "galleries"], ("art", "art_gallery")),
    **dict.fromkeys(["art", "exhibition", "exhibitions"], ("art", None)),
    **dict.fromkeys(["park", "parks"], ("outdoor", "park")),
    **dict.fromkeys(["garden", "gardens", "beach", "beaches", "hike", "hikes", "hiking", "nature", "outdoors", "viewpoint"], ("outdoor", None)),
}

# Words that describe a search rather than name what's searched for.
FILLER_WORDS = {
    "the", "and", "for", "with", "near", "best", "good", "great", "top", "cool", "hip",
    "trendy", "cheap", "spot", "spots", "place", "places", "things", "thing",
}


@dataclass(frozen=True)
class SearchIntent:
    category: str  # one of the app's categories: cafe, food, art, outdoor, nightlife
    google_type: Optional[str]  # Places API (New) type for strict filtering, if safe


def search_words(query: str) -> list[str]:
    """Lower-cased words of a query, without filler like "best" or "trendy"."""
    words = re.findall(r"[\wÀ-ɏ'-]+", query.lower())
    return [w for w in words if len(w) > 2 and w not in FILLER_WORDS]


def detect_intent(query: str) -> Optional[SearchIntent]:
    """The kind of place the query asks for, from its first recognised word."""
    for word in search_words(query):
        if word in SEARCH_TERMS:
            category, google_type = SEARCH_TERMS[word]
            return SearchIntent(category, google_type)
    return None
