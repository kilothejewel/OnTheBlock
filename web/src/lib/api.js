// Thin wrapper around fetch for the On the Block API.

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1';

if (import.meta.env.PROD && !import.meta.env.VITE_API_BASE) {
  // A production build without VITE_API_BASE would send every request to the
  // visitor's own computer. Set it in the host's build settings (e.g. Netlify).
  console.error('VITE_API_BASE was not set at build time; API calls will go to localhost and fail.');
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status; // 0 means the server could not be reached
  }
}

// Sends a JSON request and returns the parsed body (null for 204).
// Throws ApiError with the server's `detail` message when it is a readable string.
export async function apiFetch(path, { token, method = 'GET', body } = {}) {
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
