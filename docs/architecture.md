# Architecture

On the Block is an API-first web app: a React site talks to a FastAPI backend, which owns all data and every call to Google and OpenAI. A future mobile app would use the same API.

```text
 Browser
   │
   ▼
 web/  (Vite + React, Netlify)
   │  HTTPS + JWT bearer token
   ▼
 app/  (FastAPI, Render) ──► Google Places API (New)   Places, photos, opening hours
   │                    └──► OpenAI                    writes Plans from candidate Places
   ▼
 Postgres (Neon in production; SQLite locally and in tests)
```

## Backend: `app/`

| Folder | What it holds |
|---|---|
| `core/` | Settings (env vars prefixed `OTB_`), the database engine, JWT security, rate limiting, and the list of supported cities with their currency |
| `models/` | SQLAlchemy tables: users, saved places (`hotspots`), plans (`itineraries`) |
| `schemas/` | Pydantic request and response shapes |
| `routers/` | HTTP endpoints: `auth`, `places`, `hotspots` (Saved places), `itineraries` (Plans) |
| `services/` | Google Places lookups, the Plan generator, search-intent parsing, and Demo data |

Some code names still predate the [glossary](../GLOSSARY.md): `Itinerary` is a Plan, an itinerary's `items` are its Stops, and `Hotspot` is a Saved place.

### Cities

`app/data/cities.yaml` is the city registry: name, province, currency, time zone, centre, metro `bounds` and `launch_status` (`live`, `beta` or `hidden`) per city. It's validated when the API starts; a broken file stops startup with the reason. Only `live` and `beta` cities take new Plans and searches; a `hidden` city's saved Plans still open. Google Text Search is restricted to a city's `bounds`, and results outside them are dropped. `GET /api/v1/cities` lists the visible cities, South Africa first, for the web and mobile pickers.

### How a Plan is generated

The chat planner is a fixed pipeline ([ADR 0006](adr/0006-planner-pipeline.md)), being built in SA2 (#78):

```
chat message
  → intake (LLM, strict JSON; rules fallback)   → BriefPatch + next action
  → Brief (typed: city, Date, Mode, Area, Interests, budget in rands)
  → skeleton (code)                             → Slots with times, from Mode, Interests and sunset
  → retrieve + score (code)                     → candidates per Slot from the city's open-data catalogue
  → compose (LLM, strict JSON)                  → one candidate key per Slot from an enum, plus copy
  → live check + validate + repair (code)       → Google Place Details for the final Stops only; budget, hours, travel, safety
  → stream (Server-Sent Events)                 → the Plan, as it's built
```

The LLM runs only in intake and compose, behind one `LLMClient` (Gemini free tier, then Groq free tier, then a rules client). It never sets costs or times, and it can't invent a place: compose picks from keys we offered. Every Google and LLM call asks the free-quota guard first.

**Today** the live site still runs the v1 form planner (`app/services/itinerary.py`), which the pipeline replaces (#118):

1. The web app sends the city, Budget tier and Vibes.
2. The Plan generator asks Google Places for candidate Places for each Slot (breakfast, lunch, dinner…), avoiding repeats.
3. OpenAI picks from those candidates and writes the Plan as JSON.
4. Every Stop is checked against the candidates. A Stop whose place ID wasn't offered is kept with an "[Unverified]" prefix.

### Demo data

Without `OTB_GOOGLE_PLACES_API_KEY` or `OTB_OPENAI_API_KEY`, the matching service serves built-in Demo data for every city in the registry (`app/data/cities.yaml`), so the app runs fully with no keys. See [ADR 0003](adr/0003-no-silent-demo-fallback.md) for when Demo data may and may not be used.

### Auth and limits

- Email or username plus password, hashed with bcrypt. Sessions are signed JWT bearer tokens (PyJWT).
- Rate limits per client IP with slowapi: 100 requests a minute by default, and stricter limits on endpoints that cost money (for example 5 a minute for generating a Plan).
- Free-quota guard (`app/services/quota.py`): every Google and LLM call asks `quota.take(resource, pool=...)` first, and is skipped (the caller degrades) when the answer is no. Counts live in the `quota_usage` table, per UTC day for all pools and per UTC month for each pool (`users`, `guests`, `eval`), so every process shares them. Limits sit just under each free allowance and come from `OTB_QUOTA_LIMITS` and `OTB_QUOTA_POOL_CAPS`.

### Database

SQLAlchemy over Postgres in production and SQLite locally (`OTB_DATABASE_URL`). Alembic migrations in `migrations/versions/` own the schema; the app never creates or alters tables at startup. `python -m app.migrate` brings a database up to the latest migration, and first adopts a database built before migrations existed (it adds any missing nullable columns, then stamps it at the baseline). Tests check that the migrations produce exactly the models' schema, on SQLite and Postgres.

## Frontend: `web/`

Vite + React 19 with plain CSS and `lucide-react` icons. `VITE_API_BASE` sets which API it talks to.

## Delivery

- **CI** (`.github/workflows/ci.yml`) runs on every pull request and push to `main`: API tests against SQLite and Postgres 16, and the web app's lint and production build.
- **API:** Render deploys `main` only after CI passes (`render.yaml`), using Neon Postgres. Its start command runs `python -m app.migrate` and starts the API only if that succeeds, so a failed migration fails the deploy and the previous version keeps serving. Secrets are set in Render, never in git.
- **Web:** Netlify builds a preview for each PR and deploys `main` to https://ontheblock.netlify.app.
- **Dependabot** opens grouped monthly update PRs for Python, npm and GitHub Actions.

### Hosting on free tiers

v2 runs on free tiers only (ADR 0005), so hosting costs **USD 0 a month**. Limits as published on 16 November 2026:

| | Render free web service (today) | Google Cloud Run free allowance |
| --- | --- | --- |
| Cost | USD 0; no payment card needed | USD 0 within the allowance; **needs a billing account** |
| Idle | Spins down after **15 minutes** without traffic | Scales to zero between requests |
| Waking | About **one minute** for the first request | A few seconds (cold start) |
| Monthly allowance | **750 instance hours** per workspace; past that, every free service is suspended until the next month | 2 million requests, 180,000 vCPU-seconds and 360,000 GiB-seconds (priced at us-central1 rates; other regions use the allowance up faster) |
| Past the allowance | Suspended, never billed for instance hours; extra outbound bandwidth is billed if a card is on file | **Billed**, unless the budget alert and kill function from #44 turn billing off |
| Region | Frankfurt is the closest to South Africa | `africa-south1` (Johannesburg) is available |

The database is Neon's free Postgres, which also suspends after a few idle minutes, so the first query after a quiet spell is slower.

**What users see:** any request still waiting after 3 seconds shows "Waking up the server…" at the top of the screen until it answers (`web/src/lib/api.js`). The chat page (#103) keeps the user's message while it waits, so nothing is lost.

> **TODO(cameron): choose the host.** Render free needs no card but makes the first visitor after 15 idle minutes wait about a minute. Cloud Run wakes in seconds and can run in Johannesburg, but sits on a billing account, so it only stays free with #44's budget alert and kill function. `render.yaml` stays as it is until this is decided.
