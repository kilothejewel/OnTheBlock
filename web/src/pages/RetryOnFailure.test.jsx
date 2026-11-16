// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import App from '../App';
import { resetCities } from '../lib/cities';

const SESSION = { token: 'header.payload.signature', username: 'sam' };
const CITIES = [{ slug: 'cape-town', name: 'Cape Town', province: 'Western Cape', country_code: 'ZA', currency: 'ZAR', status: 'beta' }];
const UNAVAILABLE = {
  code: 'places_unavailable', retryable: true,
  message: "We couldn't find places in Cape Town for your Plan right now. Please try again in a moment.",
};
const PLAN = {
  title: 'A day out in Cape Town', destination: 'Cape Town', budget: '$$', duration_days: 1, city: 'cape-town',
  currency: 'ZAR', demo: false, items: [{ day: 1, time: '09:00 AM', activity: 'Breakfast', location: 'Real Bistro', estimated_cost: 120, verified: true }],
};

// Answers per "METHOD /path"; a list is used up in order.
function api(routes) {
  const calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url, init = {}) => {
    const key = `${init.method || 'GET'} ${new URL(url).pathname.replace('/api/v1', '')}`;
    calls.push(key);
    const route = routes[key];
    const [status, body] = Array.isArray(route?.[0]) ? route.shift() : route || [404, { detail: 'Not found' }];
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  }));
  return calls;
}

function renderAt(path) {
  render(<MemoryRouter initialEntries={[path]}><App initialSession={SESSION} /></MemoryRouter>);
}

beforeEach(() => {
  window.scrollTo = vi.fn();
  localStorage.clear();
  resetCities();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const BASE = { 'GET /cities': [200, CITIES], 'GET /hotspots/': [200, []], 'GET /itineraries/': [200, []] };

describe('a failure that can be retried', () => {
  it('shows the message and a Retry button for a Plan, and Retry tries again', async () => {
    const calls = api({ ...BASE, 'POST /itineraries/generate': [[503, UNAVAILABLE], [200, PLAN]] });
    renderAt('/plan');

    fireEvent.click(await screen.findByRole('button', { name: /plan my day/i }));
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain(UNAVAILABLE.message);
    expect(screen.queryByText(/demo/i)).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByRole('heading', { level: 1, name: PLAN.title })).toBeTruthy();
    expect(calls.filter((c) => c === 'POST /itineraries/generate')).toHaveLength(2);
  });

  it('shows the message and a Retry button for a Discover search', async () => {
    const message = "Couldn't reach Google Places right now. Please try again.";
    api({
      ...BASE,
      'GET /hotspots/recommend': [[503, { code: 'places_unavailable', retryable: true, message, detail: message }],
        [200, [{ google_place_id: 'ChIJreal01', name: 'Real Cafe', types: 'cafe' }]]],
    });
    renderAt('/discover');

    fireEvent.submit(await screen.findByRole('search'));
    expect((await screen.findByRole('alert')).textContent).toContain(message);

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByRole('heading', { name: 'Real Cafe' })).toBeTruthy();
  });

  it('offers Retry when the server cannot be reached at all', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      if (String(url).endsWith('/itineraries/generate')) throw new TypeError('Failed to fetch');
      const path = new URL(url).pathname.replace('/api/v1', '');
      const [status, body] = BASE[`GET ${path}`] || [404, {}];
      return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
    }));
    renderAt('/plan');
    fireEvent.click(await screen.findByRole('button', { name: /plan my day/i }));
    expect((await screen.findByRole('alert')).textContent).toMatch(/couldn't reach the server/i);
    expect(screen.getByRole('button', { name: 'Retry' })).toBeTruthy();
  });
});
