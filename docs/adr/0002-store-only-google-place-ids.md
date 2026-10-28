# Store only Google place IDs

Google Maps Platform terms allow a place ID to be stored indefinitely but restrict caching other Place content (name, rating, address, photos, coordinates). So Saved places and the Stops of saved Plans persist only the place ID plus our own data (AI-written text, cost estimates, the user's choices), and Place details are fetched when shown, behind a short-lived cache. We considered keeping the fields and refreshing them every 30 days, but rejected it: it's easier to get wrong, and a repo strangers will copy should model the compliant pattern.

## Consequences

- Showing a saved item with a cold cache costs a Places API call, so spend controls and caching matter.
- Wherever Google data is shown, the "Google Maps" attribution and photo-author credits must be shown too.
- At the time of writing the `hotspots` table and saved itinerary items still store Google fields; migrating them is on the roadmap.
