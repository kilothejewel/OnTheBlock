# Planner pipeline with schema-locked LLM steps

Status: Accepted, 9 November 2026 (updated for the free tier)

The chat planner is a fixed pipeline of steps. Code does everything that can be checked (times, costs, distances, opening hours, which places exist), and the LLM is called in only two places, each with a strict JSON schema for its output:

1. **Intake (LLM).** The chat message becomes a `BriefPatch` and the next action (ask a question, or plan). The rules matcher (`match_interests`, money and date parsing) runs first and is also the fallback.
2. **Brief.** The patch is merged into the typed Brief: city, Date, Mode, Area, Interests, budget in rands.
3. **Skeleton (code).** Slots with start times and lengths from the Mode, the Interests and sunset.
4. **Retrieve and score (code).** Candidates per Slot come from the city's open-data places catalogue (Overture Maps and Foursquare OS Places, #119) and are scored from catalogue signals. Google isn't called for candidates.
5. **Compose (LLM).** For each Slot, the LLM picks one candidate key from a JSON-schema `enum` of that Slot's candidates (`s1c1`, `s1c2`…) and writes the copy. Code maps the keys back to place IDs, and validates the output again whatever the provider promises.
6. **Live check, validate and repair (code).** Google Place Details is called only for the final Stops, through the free-quota guard (#121), to confirm opening hours and price. Then budget, hours, travel time and safety are checked, and failing Stops are swapped with a deterministic repair loop (at most 10 swaps).
7. **Stream.** The Plan and its progress go to the web as Server-Sent Events.

**Costs and times never come from the LLM.** Costs come from curated data and the live check (#95, #96, #97). Times come from the skeleton and the validator. A made-up place can't appear at all: the compose schema only allows keys we offered.

**Providers** sit behind one `LLMClient` seam (#90) with two methods, `extract_brief` and `compose_plan`. It tries the Gemini free tier, then the Groq free tier, then a rules client that needs no model, so a Plan still comes back when every provider is down or out of quota. Model names live in config and are chosen by the eval harness (#106), not in code. Every call asks the quota guard first. No prompt carries a user's email, name or phone number.

## Rejected: a tool-calling agent loop

An agent that calls search, details and pricing tools until it decides it's done was considered and rejected:

| | Fixed pipeline (chosen) | Agent loop |
| --- | --- | --- |
| Quality | Predictable: each step tested on its own and in the eval harness | Varies with each run's choices; hard to test |
| Latency | 8–15 s: two LLM calls, code in between | 20–60 s: many sequential model and tool calls |
| Cost and quota | Fixed per Plan: two LLM calls, at most `OTB_LIVE_CHECKS_PER_PLAN` Google calls | Unbounded: the model decides how many calls to make, which the free quota can't absorb |
| Made-up places | Impossible: compose can only choose offered keys | Possible; caught only by a later check, if at all |
| Flexibility | New behaviour needs code: a new step or rule | Can improvise for requests nobody planned for |

The pipeline gives up some flexibility for Plans that are predictable, fast and inside the free quota. Requests the pipeline can't serve become new Interests, rules or steps, each with tests.

## Consequences

- This supersedes `app/services/itinerary.py`: OpenAI is no longer asked for free-form JSON, and its `[Unverified]` Stops (a place ID the model invented, kept with a prefix) go away, because compose can't invent one. The v1 code is removed in #118.
- Each step is its own module (`intake.py`, `skeleton.py`, `scoring.py`, `compose.py`, `validate.py`) with unit tests, and the eval harness scores the whole Plan.
- The two LLM steps take snapshot tests of their prompts and schemas, and the rules client returns the same shapes, so tests and Demo mode need no keys.
- Google is called for a handful of final Stops per Plan instead of every candidate, which keeps the live check inside the free Place Details allowance.
