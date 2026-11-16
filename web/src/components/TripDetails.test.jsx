// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import TripView from './TripView';

const TIMES = ['09:00 AM', '10:00 AM', '11:00 AM', '01:00 PM', '03:00 PM', '07:00 PM'];
const SIX_STOPS = TIMES.map((time, i) => ({
  day: 1, time, activity: `Stop ${i + 1}`,
  // Saved with only a place ID: name and address come from the details call.
  location: '', address: null, google_place_id: `ChIJstop00000${i}`, verified: true,
  description: `About stop ${i + 1}`, estimated_cost: 100,
}));
const PLAN = { id: 9, title: 'Six stops', destination: 'Cape Town', budget: '$$', duration_days: 1, currency: 'ZAR', items: SIX_STOPS };

let calls;

beforeEach(() => {
  calls = [];
  window.scrollTo = vi.fn();
  vi.stubGlobal('fetch', vi.fn(async (url) => {
    const { pathname, searchParams } = new URL(url);
    calls.push(pathname.replace('/api/v1', ''));
    if (pathname.endsWith('/places')) {
      const body = searchParams.get('ids').split(',').map((id) => ({
        google_place_id: id, name: `Real ${id.slice(-1)}`, address: `${id.slice(-1)} Long St`, source: 'google', details_available: true, types: [],
      }));
      return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }
    return new Response(JSON.stringify({ url: 'https://photo.example/x.jpg', attribution: 'Sam' }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('a saved Plan', () => {
  it('makes one details request for all its Stops and no photo request until a Stop is opened', async () => {
    render(<TripView itinerary={PLAN} mode="saved" onBack={() => {}} onDelete={() => {}} />);

    expect(await screen.findByText('Real 0')).toBeTruthy();
    expect(await screen.findByText('5 Long St')).toBeTruthy();
    expect(calls).toEqual(['/places']);

    const [firstDetails] = screen.getAllByRole('button', { name: /details/i });
    await act(async () => { fireEvent.click(firstDetails); });
    await screen.findByText('About stop 1');
    await vi.waitFor(() => expect(calls.filter((c) => c.endsWith('/photo'))).toHaveLength(1));
    expect(calls.filter((c) => c === '/places')).toHaveLength(1);
  });
});
