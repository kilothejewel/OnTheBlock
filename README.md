<p align="center"><img src="web/public/logo-mark.svg" width="72" alt="On the Block logo"></p>

<h1 align="center">On the Block</h1>

<p align="center">
  <a href="https://github.com/kilothejewel/OnTheBlock/actions/workflows/ci.yml"><img src="https://github.com/kilothejewel/OnTheBlock/actions/workflows/ci.yml/badge.svg" alt="CI status"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT license"></a>
</p>

<p align="center"><b>Discover places and plan a day or night out on a budget.</b><br>
<a href="https://ontheblock.netlify.app">Try it live →</a></p>

<!-- Screenshot: add docs/screenshot.png and uncomment.
<p align="center"><img src="docs/screenshot.png" width="800" alt="On the Block planning a night out in Cape Town"></p>
-->

On the Block finds real places in Miami, London, Cape Town, Johannesburg and Tokyo, and turns them into a Plan: a short run of Stops near each other, priced in local currency for your Budget tier. Save the places you like and keep your Plans in Trips.

## Quickstart

No API keys needed: without them the app runs on built-in Demo data.

```bash
git clone https://github.com/kilothejewel/OnTheBlock.git && cd OnTheBlock
pip install -r requirements.txt && cp .env.template .env   # then set OTB_DATABASE_URL to SQLite, see CONTRIBUTING.md
uvicorn app.main:app --reload
cd web && npm install && cp .env.example .env && npm run dev   # in a second terminal
```

Open http://localhost:5273. Full setup, including real data and tests, is in [CONTRIBUTING.md](CONTRIBUTING.md).

## Stack

A **FastAPI** + SQLAlchemy API (Postgres, or SQLite locally) behind a **Vite + React** site, using the **Google Places API (New)** for places and photos and **OpenAI** to write Plans. Deployed on Render, Neon and Netlify, with GitHub Actions CI on every pull request.

## Docs

- [Contributing](CONTRIBUTING.md): setup, tests, workflow, project rules
- [Architecture](docs/architecture.md): how the pieces fit together
- [Roadmap](docs/roadmap.md): what's next
- [Glossary](GLOSSARY.md): the words we use
- [Decisions](docs/adr/): why some things are the way they are

## License

[MIT](LICENSE)
