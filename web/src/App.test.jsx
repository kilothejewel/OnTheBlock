// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { BrowserRouter, MemoryRouter } from 'react-router';
import App from './App';
import { resetCities } from './lib/cities';

const TOKEN = 'header.payload.signature';
const SIGNED_IN = { token: TOKEN, username: 'sam' };
const SIGNED_OUT = { token: '', username: '' };

const TRIP = {
  id: 7,
  user_id: 1,
  title: 'A day out in Cape Town',
  destination: 'Cape Town',
  budget: '$$',
  duration_days: 1,
  city: 'cape-town',
  currency: 'ZAR',
  created_at: '2026-11-15T10:00:00',
  items: [{ day: 1, time: '09:00 AM', activity: 'Breakfast', estimated_cost: 120, location: 'Test Bistro', verified: false }],
};

// A fake API: maps "METHOD /path" to [status, body].
function fakeApi(routes) {
  const calls = [];
  const fetchMock = vi.fn(async (url, init = {}) => {
    const path = new URL(url).pathname.replace('/api/v1', '');
    const key = `${init.method || 'GET'} ${path}`;
    calls.push(key);
    const [status, body] = routes[key] || [404, { detail: 'Not found' }];
    return new Response(status === 204 ? null : JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', fetchMock);
  return calls;
}

const CITIES = [
  { slug: 'cape-town', name: 'Cape Town', province: 'Western Cape', country_code: 'ZA', currency: 'ZAR', status: 'beta' },
  { slug: 'durban', name: 'Durban', province: 'KwaZulu-Natal', country_code: 'ZA', currency: 'ZAR', status: 'beta' },
  { slug: 'london', name: 'London', province: 'England', country_code: 'GB', currency: 'GBP', status: 'beta' },
];

const LIBRARY = {
  'GET /cities': [200, CITIES],
  'GET /hotspots/': [200, []],
  'GET /itineraries/': [200, [TRIP]],
};

function renderAt(path, session, routes = LIBRARY) {
  const calls = fakeApi(routes);
  render(
    <MemoryRouter initialEntries={[path]}>
      <App initialSession={session} />
    </MemoryRouter>,
  );
  return calls;
}

const heading = (name) => screen.findByRole('heading', { level: 1, name });

beforeEach(() => {
  window.scrollTo = vi.fn();
  localStorage.clear();
  resetCities();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('every screen has a URL', () => {
  it.each([
    ['/discover', "What's good on the block?"],
    ['/plan', 'Plan a day out on your budget'],
    ['/trips', 'Saved trips'],
    ['/saved', 'Saved places'],
  ])('opening %s (as on a refresh) shows that screen', async (path, title) => {
    renderAt(path, SIGNED_IN);
    expect(await heading(title)).toBeTruthy();
  });

  it('sends / to Discover', async () => {
    renderAt('/', SIGNED_OUT);
    expect(await heading("What's good on the block?")).toBeTruthy();
  });

  it('shows a clean page for an unknown address', async () => {
    renderAt('/nowhere', SIGNED_OUT);
    expect(await screen.findByText('Page not found')).toBeTruthy();
  });
});

describe('signed-out visitors', () => {
  it.each([
    ['/discover', "What's good on the block?"],
    ['/plan', 'Plan a day out on your budget'],
  ])('can open %s', async (path, title) => {
    const calls = renderAt(path, SIGNED_OUT);
    expect(await heading(title)).toBeTruthy();
    expect(screen.getByRole('button', { name: /log in/i })).toBeTruthy();
    expect(calls).toEqual(['GET /cities']); // nothing of an account's to load for a visitor
  });

  it.each(['/trips', '/trips/7', '/saved'])('are sent from %s to /login', async (path) => {
    renderAt(path, SIGNED_OUT);
    expect(await heading('Welcome back')).toBeTruthy();
  });

  it('come back to the account screen they asked for after logging in', async () => {
    renderAt('/trips/7', SIGNED_OUT, {
      ...LIBRARY,
      'POST /auth/login': [200, { access_token: TOKEN, token_type: 'bearer' }],
      'GET /auth/me': [200, { id: 1, username: 'sam', email: 'sam@example.com' }],
    });
    await heading('Welcome back');

    fireEvent.change(screen.getByLabelText('Email or username'), { target: { value: 'sam' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'supersecret123' } });
    fireEvent.click(screen.getByRole('button', { name: /^log in$/i }));

    expect(await heading(TRIP.title)).toBeTruthy();
  });

  it('are asked to log in when they search from Discover', async () => {
    renderAt('/discover', SIGNED_OUT);
    await heading("What's good on the block?");

    fireEvent.submit(screen.getByRole('search'));

    expect(await heading('Welcome back')).toBeTruthy();
  });
});

describe('/trips/:id', () => {
  it('opens that Trip directly', async () => {
    renderAt('/trips/7', SIGNED_IN);
    expect(await heading(TRIP.title)).toBeTruthy();
  });

  it('shows "Trip not found" for a Trip that is not yours', async () => {
    const calls = renderAt('/trips/99', SIGNED_IN, { ...LIBRARY, 'GET /itineraries/99': [404, { detail: 'Itinerary not found or unauthorized to view' }] });
    expect(await screen.findByText('Trip not found')).toBeTruthy();
    expect(calls).toContain('GET /itineraries/99');
  });

  it('shows "Trip not found" for an id that is not a number', async () => {
    renderAt('/trips/abc', SIGNED_IN);
    expect(await screen.findByText('Trip not found')).toBeTruthy();
  });

  it('goes back to Trips from a Trip', async () => {
    renderAt('/trips/7', SIGNED_IN);
    await heading(TRIP.title);
    fireEvent.click(screen.getByRole('button', { name: /all trips/i }));
    expect(await heading('Saved trips')).toBeTruthy();
  });
});

describe('the browser back button', () => {
  it('moves between screens', async () => {
    window.history.replaceState(null, '', '/discover');
    fakeApi(LIBRARY);
    render(
      <BrowserRouter>
        <App initialSession={SIGNED_IN} />
      </BrowserRouter>,
    );
    await heading("What's good on the block?");

    const [tripsTab] = screen.getAllByRole('button', { name: 'Trips' });
    fireEvent.click(tripsTab);
    expect(await heading('Saved trips')).toBeTruthy();
    expect(window.location.pathname).toBe('/trips');

    await act(async () => {
      window.history.back();
      await new Promise((resolve) => window.addEventListener('popstate', resolve, { once: true }));
    });
    expect(await heading("What's good on the block?")).toBeTruthy();
    expect(window.location.pathname).toBe('/discover');
  });
});

describe('cities', () => {
  it('come from GET /cities, South Africa first', async () => {
    renderAt('/plan', SIGNED_OUT);
    await heading('Plan a day out on your budget');
    const chips = await screen.findAllByRole('radio', { name: /Cape Town|Durban|London/ });
    expect(chips.map((c) => c.textContent)).toEqual(['Cape Town', 'Durban', 'London']);
    expect(screen.getByRole('radio', { name: 'Cape Town' }).getAttribute('aria-checked')).toBe('true');
  });

  it('fall back to the first listed city when the remembered one is no longer listed', async () => {
    localStorage.setItem('otb_city', 'miami');
    renderAt('/plan', SIGNED_OUT);
    const capeTown = await screen.findByRole('radio', { name: 'Cape Town' });
    expect(capeTown.getAttribute('aria-checked')).toBe('true');
  });
});
