# On the Block

On the Block helps people discover places in a city and plan a day or night out on a budget.

## Planning

**Plan**:
One generated outing in one city: an ordered set of Stops for a single Day out or Night out.
_Avoid_: Itinerary, trip (for a single outing)

**Mode**:
Whether a Plan is a Day out or a Night out.
_Avoid_: Vibe, nightlife flag

**Day out**:
A Plan that runs through the daytime, from morning into the evening.

**Night out**:
A Plan that runs through the evening and into the night.

**Area**:
A neighbourhood within a city that a Plan stays inside, such as Shoreditch, Shibuya or Maboneng.
_Avoid_: District, zone, region

**Vibes**:
Optional free-text taste a user gives a Plan, such as "art, vegan, rooftop". It shapes which Places are picked, never the Mode.
_Avoid_: Preferences, tags

**Date**:
The calendar day a Plan is for. Opening hours are checked against it.

**Budget tier**:
How much a user wants to spend, as $ (cheap), $$ (moderate) or $$$ (luxury).
_Avoid_: Price range, budget amount

**Stop**:
One Place at one time within a Plan, with a per-person cost estimate.
_Avoid_: Item, activity, entry

**Slot**:
The role a Stop fills in a Plan, such as breakfast, activity, lunch, dinner or nightlife.
_Avoid_: Category (for this meaning)

**Trip**:
Where a user's saved Plans live. A collection, not a separate kind of outing.
_Avoid_: Itinerary

## Places

**Place**:
A real venue or landmark in a city, as known to Google Places.
_Avoid_: Spot, venue, location

**Saved place**:
A Place a user has chosen to keep.
_Avoid_: Hotspot, favourite

## Access

**Guest account**:
A shared one-click login on the live site that gets real Plans under a small shared daily cap.
_Avoid_: Demo account, demo user

**Demo data**:
Built-in sample Places and Plans shown when the app has no API keys, always labelled as such.
_Avoid_: Fallback data, mock data
