# Roadmap

The goal: a launch-ready app for planning a **Day out** or **Night out** on a budget in five cities (Miami, London, Cape Town, Johannesburg, Tokyo). Terms follow the [glossary](../GLOSSARY.md). Individual tasks live in [GitHub Issues](https://github.com/kilothejewel/OnTheBlock/issues); look for `good first issue` and `help wanted`.

| Step | What | Status |
|---|---|---|
| 1 | City picker, Google Places API (New), real photos, local currency, Demo data per city | Done |
| 1a | Contributor docs: this roadmap, guide, glossary, ADRs, license | In progress |
| 1b | Alembic migrations | Done |
| 1c | Store only Google place IDs, add Google attribution | Planned |
| 2 | Day out and Night out Plans | Planned |
| 3 | Reliable planner | Planned |
| 4 | Trending this week | Planned |
| 5 | Launch polish | Planned |

## 1b. Alembic migrations

Replaced startup `create_all` with Alembic: a baseline migration matching the existing tables, tested in CI on SQLite and Postgres and run before the API starts on deploy. Databases built before Alembic are adopted automatically. Steps 1c and 2 both change the schema, so this came first.

## 1c. Store only Google place IDs

Saved places and the Stops of saved Plans keep only the place ID plus our own data, and fetch Place details when shown, behind a short cache ([ADR 0002](adr/0002-store-only-google-place-ids.md)). Every view showing Google data gets the "Google Maps" attribution and photo credits.

## 2. Day out and Night out

A Plan becomes one outing, with a **Mode**:

- **Day out** (about 09:00–18:00): breakfast or coffee, morning activity, lunch, afternoon activity.
- **Night out** (about 19:00–late): dinner, drinks, late venue.

Rules:

- **Area:** each city gets a list of Areas. The user picks one, or the planner does. Each Stop is within about a 20-minute walk (about 1.5 km) of the one before.
- **Date:** from today up to 7 days ahead. Opening hours are checked against the Date and each Stop's time:
  - If a Place is closed, another open Place is swapped in for the same Slot.
  - If no open Place exists for a Slot, the Stop is dropped and the user is told why.
  - If Google has no hours for a Place, the Stop stays, marked "hours not confirmed".
- **Vibes:** optional free text that shapes which Places are picked. It replaces the old nightlife keyword check.
- Existing multi-day plans stay viewable, labelled as an older format.
- Editing single Stops is out of scope; users regenerate the whole Plan.

## 3. Reliable planner

- OpenAI must return a fixed format (structured outputs). Made-up Stops are rejected, not shown as "[Unverified]".
- No silent fallback: with keys set, a failure shows a clear error and a retry button. Demo data appears only when keys aren't set, with a badge ([ADR 0003](adr/0003-no-silent-demo-fallback.md)).
- Spend controls, all set in config: Google API daily quotas and a budget alert, an OpenAI monthly limit, about 5 new Plans per user per day, and no live calls for visitors who aren't signed in.
- **Guest account:** a one-click login on the live site with a small shared daily cap and a "daily limit reached" message.

## 4. Trending this week

A "Trending this week" section per city, from OpenAI web search, with sources shown.

## 5. Launch polish

A README with screenshots, desktop text tabs, a city hero, hearts on Stops, a profile menu, a livelier Discover page and stronger auth.

## Later ideas

Not planned yet; open an issue to discuss.

- Each city's own time zone and local hours.
- A calendar in the profile for picking days to visit Places, and possibly reservations.
- A budget as an amount (e.g. "R500 per person") instead of a Budget tier.
- Multi-day Trips built from several Plans.
- Editing or swapping single Stops.
- A mobile app on the same API.
