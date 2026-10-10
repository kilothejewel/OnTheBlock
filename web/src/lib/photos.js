import { apiFetch } from './api';

// place id -> Promise of { url, attribution, attribution_url } or null.
// Shared across cards so each place's photo is looked up once per session.
const cache = new Map();

function currentToken() {
  try {
    return localStorage.getItem('otb_token') || '';
  } catch {
    return '';
  }
}

export function isLivePlaceId(placeId) {
  return Boolean(placeId) && !String(placeId).startsWith('mock');
}

// A place's real Google photo, fetched through our API so the Google key stays
// on the server. Resolves to null when there is no photo (or on demo data).
export function fetchPlacePhoto(placeId) {
  if (!isLivePlaceId(placeId)) return Promise.resolve(null);
  if (!cache.has(placeId)) {
    const request = apiFetch(`/places/${encodeURIComponent(placeId)}/photo`, { token: currentToken() })
      .catch(() => null);
    cache.set(placeId, request);
  }
  return cache.get(placeId);
}
