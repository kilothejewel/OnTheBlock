// Thin wrapper around fetch for the On the Block API.
//
// The API's types are generated from its OpenAPI schema into ./api-types.ts
// (`npm run gen:api`; CI fails when they're out of date). Use them in JSDoc:
//   /** @type {import('./api').Stop} */

/** @typedef {import('./api-types').components['schemas']} Schemas */
/** @typedef {Schemas['Stop']} Stop  One entry in a Plan */
/** @typedef {Schemas['SavedStop']} SavedStop  A Stop read back from a saved Plan */
/** @typedef {Schemas['GeneratedItinerary']} GeneratedPlan  POST /itineraries/generate */
/** @typedef {Schemas['ItineraryCreate']} PlanToSave  POST /itineraries/ */
/** @typedef {Schemas['ItineraryResponse']} SavedPlan  A Plan in Trips */

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1';

if (import.meta.env.PROD && !import.meta.env.VITE_API_BASE) {
  // A production build without VITE_API_BASE would send every request to the
  // visitor's own computer. Set it in the host's build settings (e.g. Netlify).
  console.error('VITE_API_BASE was not set at build time; API calls will go to localhost and fail.');
}

export class ApiError extends Error {
  /**
   * @param {string} message
   * @param {number} status
   * @param {{ code?: string, retryable?: boolean }} [extra]
   */
  constructor(message, status, { code = '', retryable = false } = {}) {
    super(message);
    this.status = status; // 0 means the server could not be reached
    this.code = code; // e.g. "places_unavailable" on a 503
    // Worth offering a Retry: a 503 says so, and an unreachable server may wake up.
    this.retryable = retryable || status === 0 || status === 503;
  }
}

// The free host sleeps when idle and takes up to a minute to wake (#27), so
// any request still waiting after SLOW_REQUEST_MS counts as "waking up" until
// it answers. Components read it with useServerWaking().
export const SLOW_REQUEST_MS = 3000;
let slowRequests = 0;
const slowListeners = new Set();

/** @param {number} delta */
function changeSlowRequests(delta) {
  const before = slowRequests > 0;
  slowRequests = Math.max(0, slowRequests + delta);
  if (before !== slowRequests > 0) slowListeners.forEach((listener) => listener());
}

/** Whether any request has been waiting longer than SLOW_REQUEST_MS. */
export function isServerSlow() {
  return slowRequests > 0;
}

/**
 * Calls `listener` when that changes; returns the unsubscribe function.
 * @param {() => void} listener
 */
export function subscribeServerSlow(listener) {
  slowListeners.add(listener);
  return () => slowListeners.delete(listener);
}

/**
 * Sends a JSON request and returns the parsed body (null for 204).
 * Throws ApiError with the server's `detail` message when it is a readable string.
 * @param {string} path
 * @param {{ token?: string, method?: string, body?: unknown }} [options]
 * @returns {Promise<any>} Cast the result with one of the typedefs above.
 */
export async function apiFetch(path, { token, method = 'GET', body } = {}) {
  /** @type {Record<string, string>} */
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  let res;
  let flaggedSlow = false;
  const slowTimer = setTimeout(() => {
    flaggedSlow = true;
    changeSlowRequests(1);
  }, SLOW_REQUEST_MS);
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("We couldn't reach the server. Check your connection and try again.", 0);
  } finally {
    clearTimeout(slowTimer);
    if (flaggedSlow) changeSlowRequests(-1);
  }

  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    // Validation errors (422) carry a list, not a sentence; callers supply a fallback.
    // A 503 carries {code, message, retryable} (app/core/errors.py).
    const detail = typeof data?.message === 'string' ? data.message : typeof data?.detail === 'string' ? data.detail : '';
    throw new ApiError(detail, res.status, { code: data?.code, retryable: data?.retryable === true });
  }
  return data;
}
