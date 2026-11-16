# South Africa first

Status: Accepted, 6 November 2026

South African cities are the product. On the Block becomes a chat planner for a day or night out in South Africa, priced in rands, rather than a planner spread thinly over five cities on three continents. A product that knows Cape Town well beats one that knows five cities a little, and the people building and reviewing it live there.

- **Wave one: Cape Town.** **Wave two: Johannesburg, Durban, Pretoria, then Stellenbosch and the Winelands.**
- **Miami, London and Tokyo stay, as beta.** They run the same pipeline but get no curated cost data and no quality gate, and they are labelled "Beta: less checked".
- **Every city has a `launch_status`** in the city registry (`app/data/cities.yaml`, #85): `live`, `beta` or `hidden`. Only `live` and `beta` cities take new Plans; a `hidden` city's saved Plans still open.
- **An SA city goes `live` only after it passes the quality gate** (SA4: hard checks on at least 95% of its golden Briefs, a judge average of at least 4 out of 5, and local reviewers saying "I'd do this" for at least 80% of Plans). Until then it is `beta`.
- **Budgets are in the city's own currency** (ZAR in South Africa) and **times are on the city's clock** (`Africa/Johannesburg`), never the server's.

v2 also runs on free tiers only (decided 7 November 2026): free Google Places allowances guarded by a quota guard, free-tier LLMs, and open data for the places catalogue and guides. [ADR 0007](0007-data-sources-and-licences.md) lists the data sources and their licences.

## Consequences

- The city registry replaces the hard-coded city list, with real metro bounds and time zones (#85).
- Cost data, Areas and the quality gate are built for Cape Town first; other cities stay `beta` until they have their own.
- The international cities cost little to keep, because they share the pipeline. They can be hidden later by setting `launch_status: hidden`, without losing anyone's saved Plans.
- The v1 form planner and its multi-day, Budget-tier Plans are retired once the chat planner ships (#118). Older saved Plans stay readable.
