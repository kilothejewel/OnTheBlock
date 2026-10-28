# Contributing to On the Block

Thanks for helping out. This guide gets you from a fresh clone to an open pull request. You don't need any API keys: without them the app runs on built-in **Demo data** for its five cities (Miami, London, Cape Town, Johannesburg, Tokyo).

Before you start, skim:

- [GLOSSARY.md](GLOSSARY.md): the words we use (Plan, Stop, Mode, Saved place…). Please use them in code, issues and PRs.
- [docs/architecture.md](docs/architecture.md): how the pieces fit together.
- [docs/roadmap.md](docs/roadmap.md): what's being built next.
- [docs/adr/](docs/adr/): decisions that are deliberate and shouldn't be "fixed".

## Run it locally

You need Python 3.13 (see `.python-version`; 3.11+ works), Node.js 22 (18+ works) and npm. Postgres is optional.

### API (FastAPI)

```bash
python -m venv .venv
source .venv/Scripts/activate        # Windows Git Bash; use .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.template .env
```

Then edit `.env`:

1. **Use SQLite:** uncomment `OTB_DATABASE_URL=sqlite:///./ontheblock.db`. Otherwise the app tries to reach Postgres with the placeholder `OTB_POSTGRES_*` values.
2. **Set a secret:** replace `OTB_SECRET_KEY` with the output of `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
3. **Leave the API key placeholders as they are** to run on Demo data.

Create the database tables, then start the API:

```bash
python -m app.migrate                # applies the migrations in migrations/; also adopts a database built before them
uvicorn app.main:app --reload
```

The API runs on http://localhost:8000, with interactive docs at http://localhost:8000/docs.

### Web app (Vite + React)

```bash
cd web
npm install
cp .env.example .env    # VITE_API_BASE points at the local API by default
npm run dev
```

The site runs on http://localhost:5273.

### Using real data (optional)

Only needed if you're working on the live Google Places or OpenAI paths. Use **your own** keys; the project never shares its keys.

- `OTB_GOOGLE_PLACES_API_KEY`: a Google Maps Platform key with **Places API (New)** enabled.
- `OTB_OPENAI_API_KEY`: an OpenAI API key.

Both cost money per call. Before adding them, set a daily quota on the Places API and a budget alert in Google Cloud, and a monthly spending limit on your OpenAI account.

## Tests and checks

CI runs all of these on every pull request, and a PR can't merge until they pass.

```bash
pytest                      # API tests on in-memory SQLite, with Google and OpenAI mocked
cd web && npm run lint && npm run build
```

To run the API tests against Postgres too, point `OTB_TEST_DATABASE_URL` at a test database, e.g. `postgresql://user:pass@localhost:5432/otb_test`.

Tests should exercise behaviour through the API (see `tests/test_itineraries.py` and `tests/test_places.py`), never call real external services, and pass without any API keys.

## Workflow

1. Find or open an issue. Good starting points are labelled `good first issue` or `help wanted`. Comment so others know you're on it.
2. Branch off `main`, e.g. `feat/night-out-mode` or `fix/login-redirect`. `main` is protected, so all changes go through pull requests.
3. Commit using [Conventional Commits](https://www.conventionalcommits.org/), as the history already does: `feat: …`, `fix(web): …`, `docs: …`, `chore(deps): …`.
4. Open a PR and fill in the template. Netlify builds a preview site for it.
5. Once CI passes and it's reviewed, it's merged. Render deploys the API and Netlify deploys the site from `main` automatically.

## Project rules

- **Use the glossary.** If you need a word that isn't in [GLOSSARY.md](GLOSSARY.md), raise it in your PR rather than inventing a synonym.
- **Never commit keys or `.env` files.** `.env` is git-ignored; keep it that way.
- **Store only Google place IDs.** Don't persist Google's names, ratings, addresses, photos or coordinates; fetch them when shown ([ADR 0002](docs/adr/0002-store-only-google-place-ids.md)).
- **Credit Google.** Wherever Google Places data or photos appear, show the "Google Maps" attribution and the photo author's credit.
- **No silent Demo data.** Demo data is only for running without keys and is always labelled. If a live call fails, show an error ([ADR 0003](docs/adr/0003-no-silent-demo-fallback.md)).
- **Mind the cost.** Endpoints that call Google or OpenAI need a strict rate limit (`@limiter.limit(...)`) and should never run for visitors who aren't signed in.

## License

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE).
