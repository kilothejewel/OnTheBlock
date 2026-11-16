# Data sources and licences

Status: Accepted, 7 November 2026

v2 runs on free tiers only, so its local knowledge comes from open data and our own notes, never from paid APIs or scraped sites. Each source below was chosen because its licence lets us store and show what we need, and each is listed with its licence and pinned release in `app/data/sources.yaml`.

| Use | Source | Licence / terms | What we store |
| --- | --- | --- | --- |
| Places catalogue (#119) | [Overture Maps places](https://docs.overturemaps.org/guides/places/) | [CDLA Permissive 2.0](https://docs.overturemaps.org/attribution/) (rows from Foursquare are Apache 2.0) | The rows we use, with source ids |
| Places catalogue (#119) | [Foursquare OS Places](https://docs.foursquare.com/data-products/docs/access-fsq-os-places) | [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0) | The rows we use, with source ids |
| Guide text (#122) | [Wikivoyage](https://en.wikivoyage.org/wiki/Wikivoyage:Copyleft), [Wikipedia](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use) | CC BY-SA 4.0: credit and a link; adapted text is shared under the same licence | Chunks with URL, revision and licence |
| Local picks (#122, #124) | Our curated notes and trending list | Ours | All of it |
| Live check (#93) | [Google Places API (New)](https://developers.google.com/maps/documentation/places/web-service/policies) | [Google Maps Platform terms](https://cloud.google.com/maps-platform/terms) | Place IDs only; live fields are never stored ([ADR 0002](0002-store-only-google-place-ids.md)) |
| Weather (#114) | [Open-Meteo](https://open-meteo.com/en/licence) | CC BY 4.0; the [free API](https://open-meteo.com/en/terms) is for non-commercial use, under 10,000 calls a day | Nothing beyond a short cache |

Each licence was checked on the source's own page on 16 November 2026.

- **The Reddit Data API is not used.** Commercial use needs Reddit's approval and a contract, and using its data for machine learning is restricted. reddit.com is not a source, scraped or otherwise. Revisit only with an agreement in place.
- **No paid web search.** The weekly OpenAI web-search job planned for "Trending this week" is dropped; the hand-kept trending list (#124) replaces it.
- **Free-tier LLM prompts may be used by the provider and read by people.** They never carry personal data: no email, name or phone number (#90).
- **Credits.** The web footer has a "Data and guides" line: Overture Maps Foundation, Foursquare, Wikivoyage, Wikipedia, Open-Meteo and Google, each linked. Every Stop whose copy uses guide text shows its source link (#98, #113). Google data keeps its own attribution where it's shown (#32).

## Consequences

- `app/data/sources.yaml` is the list of record. A new source needs an entry there, a licence check and, if it's shown to users, a credit in the footer. A test checks every credit is in the footer.
- The monthly refresh job (#112) moves the pinned Overture and Foursquare releases forward and updates `release`.
- Guide text adapted into Stop copy is CC BY-SA, so the copy carries its source link and the same licence.
- Open-Meteo's free API is non-commercial. If On the Block ever earns money, weather needs Open-Meteo's paid API or a self-hosted instance.
