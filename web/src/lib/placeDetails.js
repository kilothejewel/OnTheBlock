import { apiFetch } from './api';
import { isLivePlaceId } from './photos';

// Display details for places (GET /places?ids=, #29). Calls made in the same
// tick are batched into one request per 20 IDs, so a screen of Stops makes a
// single call. Nothing is kept between screens: only place IDs may be stored.
const MAX_IDS = 20;
let queue = new Map(); // place id -> [resolve]
let scheduled = false;

function currentToken() {
  try {
    return localStorage.getItem('otb_token') || '';
  } catch {
    return '';
  }
}

async function flush() {
  scheduled = false;
  const batch = queue;
  queue = new Map();
  const ids = [...batch.keys()];
  for (let i = 0; i < ids.length; i += MAX_IDS) {
    const chunk = ids.slice(i, i + MAX_IDS);
    let details;
    try {
      details = await apiFetch(`/places?ids=${chunk.map(encodeURIComponent).join(',')}`, { token: currentToken() });
    } catch {
      details = [];
    }
    const byId = new Map((details || []).map((d) => [d.google_place_id, d]));
    chunk.forEach((id) => batch.get(id).forEach((resolve) => resolve(byId.get(id) || null)));
  }
}

/**
 * One place's details, batched with every other call in this tick. Resolves to
 * null for Demo or missing places, or when the request fails.
 * @param {string} placeId
 */
export function fetchPlaceDetails(placeId) {
  if (!isLivePlaceId(placeId)) return Promise.resolve(null);
  return new Promise((resolve) => {
    if (!queue.has(placeId)) queue.set(placeId, []);
    queue.get(placeId).push(resolve);
    if (!scheduled) {
      scheduled = true;
      setTimeout(flush, 0);
    }
  });
}
