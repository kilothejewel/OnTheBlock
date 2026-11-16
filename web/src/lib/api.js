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
   */
  constructor(message, status) {
    super(message);
    this.status = status; // 0 means the server could not be reached
  }
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
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("We couldn't reach the server. Check that the API is running and try again.", 0);
  }

  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    // Validation errors (422) carry a list, not a sentence; callers supply a fallback.
    const detail = typeof data?.detail === 'string' ? data.detail : '';
    throw new ApiError(detail, res.status);
  }
  return data;
}
