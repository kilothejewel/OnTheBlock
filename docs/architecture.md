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

### How a Plan is generated

1. The web app sends the city, Budget tier and Vibes.
2. The Plan generator asks Google Places for candidate Places for each Slot (breakfast, lunch, dinner…), avoiding repeats.
3. OpenAI picks from those candidates and writes the Plan as JSON.
4. Every Stop is checked against the candidates. A Stop whose place ID wasn't offered is treated as made up.

The [roadmap](roadmap.md) changes this flow in step 2 (Mode, Area, Date, opening hours) and step 3 (structured outputs, no silent fallback).

### Demo data

Without `OTB_GOOGLE_PLACES_API_KEY` or `OTB_OPENAI_API_KEY`, the matching service serves built-in Demo data for the five cities, so the app runs fully with no keys. See [ADR 0003](adr/0003-no-silent-demo-fallback.md) for when Demo data may and may not be used.

### Auth and limits

- Email or username plus password, hashed with bcrypt (passlib). Sessions are signed JWT bearer tokens (python-jose).
- Rate limits per client IP with slowapi: 100 requests a minute by default, and stricter limits on endpoints that cost money (for example 5 a minute for generating a Plan).

### Database

SQLAlchemy over Postgres in production and SQLite locally (`OTB_DATABASE_URL`). Tables are currently created at startup with `create_all`, which can't change existing tables; moving to Alembic migrations is on the [roadmap](roadmap.md).

## Frontend: `web/`

Vite + React 19 with plain CSS and `lucide-react` icons. `VITE_API_BASE` sets which API it talks to.

## Delivery

- **CI** (`.github/workflows/ci.yml`) runs on every pull request and push to `main`: API tests against SQLite and Postgres 16, and the web app's lint and production build.
- **API:** Render deploys `main` only after CI passes (`render.yaml`), using Neon Postgres. Secrets are set in Render, never in git.
- **Web:** Netlify builds a preview for each PR and deploys `main` to https://ontheblock.netlify.app.
- **Dependabot** opens grouped monthly update PRs for Python, npm and GitHub Actions.
