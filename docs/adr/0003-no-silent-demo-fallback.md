# No silent fallback to Demo data

Demo data is used only when the app has no API keys (local development, contributors without keys), and it is always labelled as Demo data. When keys are set and a live call fails, the user gets a clear error with a retry, never Demo data passed off as a real Plan. The Guest account on the live site gets real Plans under a small shared daily cap; when the cap is reached it shows "daily limit reached" rather than falling back. We chose honesty over always returning something: a silent fallback hides outages and makes fake Plans look real to the recruiters most likely to press the button.

## Consequences

- At the time of writing the planner still falls back to Demo data on any OpenAI error; removing that is step 3 on the roadmap.
