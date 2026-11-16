# On the Block

On the Block helps people discover places in a city and plan a day or night out on a budget.

## Planning

**Plan**:
One generated outing in one city: an ordered set of Stops for a single Day out or Night out.
_Avoid_: Itinerary, trip (for a single outing)

**Brief**:
Everything someone wants from a Plan, gathered over a chat: city, Date, Mode, Area, party size, Budget amount, Interests, things to include or avoid, transport, dietary needs, access and pace (`app/schemas/brief.py`). Each chat message changes it with a patch.
_Avoid_: Request, query, preferences

**Mode**:
Whether a Plan is a Day out, a Night out or a Full day.
_Avoid_: Vibe, nightlife flag

**Day out**:
A Plan that runs through the daytime, from morning into the evening.

**Night out**:
A Plan that runs through the evening and into the night.

**Full day**:
A Plan that runs from the morning through the evening and into the night: a Day out and a Night out in one.

**Area**:
A neighbourhood within a city that a Plan stays inside, such as Shoreditch, Shibuya or Maboneng.
_Avoid_: District, zone, region

**Vibes**:
Superseded by Interests in the chat planner. Optional free-text taste the old form planner took, such as "art, vegan, rooftop"; still shown on older Plans.
_Avoid_: Preferences, tags

**Interest**:
One of a fixed set of things people plan around, such as nature, clubbing or wine, matched from what they say ("a jol", "wine farms") and listed in `app/data/interests.yaml`. Each maps to Google types and catalogue categories.
_Avoid_: Category, tag, activity type

**Date**:
The calendar day a Plan is for. Opening hours are checked against it.

**Budget amount**:
How much a user wants to spend, in the city's currency (rands in South Africa), per person or in total for the party. Part of the Brief.
_Avoid_: Budget tier, price range

**Budget tier**:
Superseded by the Budget amount in the chat planner. How much a user wanted to spend on the old form planner, as $ (cheap), $$ (moderate) or $$$ (luxury); still shown on older Plans.
_Avoid_: Price range

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

**Guest**:
Someone using the app without an Account: a session with no email, name or password that can chat and plan (one Plan a day) but can't keep Trips or Saved places. Signing up or logging in keeps their chats.
_Avoid_: Guest account, demo account, anonymous user

**Account**:
A user with a username, email and password, who can keep Trips and Saved places.
_Avoid_: Registered user, member

**Demo data**:
Built-in sample Places and Plans shown when the app has no API keys, always labelled as such.
_Avoid_: Fallback data, mock data
