# Roadmap

The goal: a **chat planner for a Day out or Night out in South Africa**, priced in rands, that a local would trust, running entirely on free tiers. Cape Town launches first, then Johannesburg, Durban, Pretoria and Stellenbosch ([ADR 0005](adr/0005-south-africa-first.md)). Miami, London and Tokyo stay available as beta. Terms follow the [glossary](../GLOSSARY.md). Individual tasks live in [GitHub Issues](https://github.com/kilothejewel/OnTheBlock/issues) under the `sa-chat` label; look for `good first issue` and `help wanted`.

## v2: the South Africa chat planner

| Step | What | Spec |
|---|---|---|
| SA1 | **South Africa foundations**: city registry with bounds and launch flags, Areas per city, the Interest taxonomy, the Brief schema, chat and Plan version tables, ADRs 0005–0007 | #77 |
| SA2 | **Chat planner core**: the free-quota guard, the LLM seam (Gemini and Groq free tiers, then rules), intake, skeleton, catalogue retrieval with a live Google check, scoring, schema-locked compose, validation and repair, the chat API and page | #78 |
| SA3 | **Budget in rands**: curated Cape Town costs, a rand range for every Stop, transport between Stops, and the budget breakdown | #79 |
| SA4 | **Quality gate**: planner traces, an eval harness with golden SA Briefs, an LLM judge, local reviewers, in-app feedback | #80 |
| SA5 | **Local knowledge and weather**: data sources and licences, a places catalogue from open data, a guide corpus with hybrid search, a hand-kept trending list, weather and sunset | #81 |
| SA6 | **Cape Town beta**: free hosting, hard caps so nothing can bill, per-user and global limits, abuse limits, guest use, the launch checklist | #82 |

A city goes from `beta` to `live` only once it passes the quality gate (SA4).

### Done so far

- Alembic migrations own the schema, and the production database was adopted (#11, #12).
- One shared HTTP client for Google (#19); typed Plan and Stop schemas with generated TypeScript types (#21); maintained auth libraries (#22).
- Real URLs in the web app with React Router (#23), and Vitest for the web (#25).
- Opening hours checked on the city's clock (#37), the free-quota guard (#121), the SA city registry (#85) and the Interest taxonomy (#86).

## Being retired

Once the chat planner and save-by-draft-id ship (#100, #101, #103), the v1 form planner goes (#118):

- `POST /itineraries/generate`, `app/services/itinerary.py` and its "[Unverified]" Stops, replaced by the pipeline in [ADR 0006](adr/0006-planner-pipeline.md)
- multi-day generation, and the Budget tier as an input (kept on old Plans)
- the form, duration and Budget-tier controls in `PlannerView.jsx`
- OpenAI, replaced by free-tier models behind one `LLMClient`

Old saved Plans stay readable, labelled as an older format. Discover and Saved places stay.

## Later ideas

Not planned yet; open an issue to discuss.

- A mobile app on the same API (the Expo spec, #46), once the chat planner is done.
- Sharing a Plan with a link, and a map view of a Plan.
- A calendar for picking days to visit Places, and possibly reservations.
- Multi-day Trips built from several Plans.
