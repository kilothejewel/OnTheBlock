# No silent fallback to Demo data

Demo data is used only when the app has no API keys (local development, contributors without keys), and it is always labelled as Demo data. When keys are set and a live call fails, the user gets a clear error with a retry, never Demo data passed off as a real Plan. The Guest account on the live site gets real Plans under a small shared daily cap; when the cap is reached it shows "daily limit reached" rather than falling back. We chose honesty over always returning something: a silent fallback hides outages and makes fake Plans look real to the recruiters most likely to press the button.

## Consequences

- Since #42, with keys set an LLM failure moves down the provider chain (Gemini, Groq, then the rules client, #90), so it still returns a Plan of real places. A failure that leaves no Plan at all (Google unreachable, no candidate places, the database down) returns 503 with `{code, message, retryable}`, and the web shows the message with a Retry button (`app/core/errors.py`).
- Demo data is served only when the app has no Google key, and is always labelled.
