from dataclasses import dataclass
from typing import Dict, Literal

# Slugs of the cities the app supports. Requests are validated against this.
CitySlug = Literal["miami", "london", "cape-town", "johannesburg", "tokyo"]


@dataclass(frozen=True)
class City:
    slug: str
    name: str
    country_code: str  # ISO 3166-1 alpha-2, used as the Places regionCode
    currency: str  # ISO 4217 code that costs are estimated in
    timezone: str
    lat: float
    lng: float
    radius_m: int  # search bias radius around the centre
    usd_rate: float  # approximate units per US dollar, for demo cost estimates only


CITIES: Dict[str, City] = {
    c.slug: c
    for c in [
        City("miami", "Miami", "US", "USD", "America/New_York", 25.7617, -80.1918, 25000, 1),
        City("london", "London", "GB", "GBP", "Europe/London", 51.5072, -0.1276, 20000, 0.78),
        City("cape-town", "Cape Town", "ZA", "ZAR", "Africa/Johannesburg", -33.9249, 18.4241, 20000, 18),
        City("johannesburg", "Johannesburg", "ZA", "ZAR", "Africa/Johannesburg", -26.2041, 28.0473, 25000, 18),
        City("tokyo", "Tokyo", "JP", "JPY", "Asia/Tokyo", 35.6762, 139.6503, 20000, 150),
    ]
}


def get_city(slug: str) -> City:
    return CITIES[slug]
