// Thin client for the OnTheBlock FastAPI backend. Every call goes through
// `request`, so error handling (readable messages, expired sessions, rate
// limits, server down) is consistent across the app.

export const API_BASE = (import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1').replace(/\/+$/, '');

export class ApiError extends Error {
  constructor(message, { status = 0, offline = false } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.offline = offline;
  }
}

const FIELD_NAMES = {
  email: 'Email',
  username: 'Username',
  password: 'Password',
  identifier: 'Email or username',
  destination: 'Destination',
  budget: 'Budget',
  duration_days: 'Number of days',
};

// FastAPI returns `detail` as a string for HTTPExceptions but as a list of
// objects for validation (422) errors. Turn either into one readable sentence.
export function describeError(detail, status) {
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : null;
        const label = FIELD_NAMES[field] || null;
        const msg = String(d.msg || 'is invalid').replace(/^Value error, /, '');
        return label ? `${label}: ${msg.charAt(0).toLowerCase()}${msg.slice(1)}` : msg;
      })
      .join(' ');
  }
  if (status === 401) return 'Your session has expired. Please log in again.';
  if (status === 429) return "You're going a little fast. Wait a minute and try again.";
  if (status >= 500) return 'Something went wrong on our side. Please try again.';
  return `Request failed (${status}).`;
}

let onUnauthorized = null;
// Called when an authenticated request comes back 401 (expired/invalid token).
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

export async function request(path, { method = 'GET', token, body, signal } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new ApiError("We can't reach the server. Check your connection and try again.", { offline: true });
  }

  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);

  if (!res.ok) {
    if (res.status === 401 && token && onUnauthorized) onUnauthorized();
    throw new ApiError(describeError(data?.detail, res.status), { status: res.status });
  }
  return data;
}

export const api = {
  login: (identifier, password) => request('/auth/login', { method: 'POST', body: { identifier, password } }),
  register: (email, username, password) => request('/auth/register', { method: 'POST', body: { email, username, password } }),
  me: (token) => request('/auth/me', { token }),

  recommend: (token, query) => request(`/hotspots/recommend?query=${encodeURIComponent(query)}`, { token }),
  listHotspots: (token) => request('/hotspots/', { token }),
  saveHotspot: (token, place) => request('/hotspots/', { method: 'POST', token, body: place }),
  removeHotspot: (token, placeId) => request(`/hotspots/${encodeURIComponent(placeId)}`, { method: 'DELETE', token }),

  generateItinerary: (token, params) => request('/itineraries/generate', { method: 'POST', token, body: params }),
  listItineraries: (token) => request('/itineraries/', { token }),
  saveItinerary: (token, itinerary) => request('/itineraries/', { method: 'POST', token, body: itinerary }),
  deleteItinerary: (token, id) => request(`/itineraries/${id}`, { method: 'DELETE', token }),
};

// Only send the fields the backend's HotspotCreate schema knows about.
export function toHotspotPayload(place) {
  return {
    google_place_id: place.google_place_id,
    name: place.name,
    rating: place.rating ?? null,
    address: place.address ?? null,
    latitude: place.latitude ?? null,
    longitude: place.longitude ?? null,
    price_level: place.price_level ?? null,
    types: place.types ?? null,
  };
}

// The AI response isn't guaranteed to echo every field back, so fill gaps
// from what the user asked for; otherwise saving would fail validation.
export function toItineraryPayload(itinerary, fallback = {}) {
  const items = Array.isArray(itinerary.items) ? itinerary.items : [];
  const days = Number(itinerary.duration_days) || Number(fallback.duration_days) || 1;
  return {
    title: (itinerary.title || '').trim() || `Trip to ${itinerary.destination || fallback.destination || 'somewhere new'}`,
    destination: itinerary.destination || fallback.destination || 'Unknown',
    budget: itinerary.budget || fallback.budget || '$$',
    duration_days: Math.max(days, ...items.map((i) => Number(i.day) || 1)),
    items,
  };
}
