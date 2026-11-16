// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import PlaceCard from './PlaceCard';
import TripView from './TripView';
import { SavedView } from './CollectionViews';

const GOOGLE_PLACE = {
  google_place_id: 'ChIJabc123def456',
  name: 'Test Bistro',
  address: '1 Long St, Cape Town',
  types: 'restaurant',
  price_level: 2,
};
const DEMO_PLACE = { ...GOOGLE_PLACE, google_place_id: 'mock_cape-town_1', name: 'Truth Coffee Roasting' };

function plan(items) {
  return {
    id: 7, title: 'A day out in Cape Town', destination: 'Cape Town', budget: '$$', duration_days: 1,
    city: 'cape-town', currency: 'ZAR', items,
  };
}

const stop = (placeId, extra = {}) => ({
  day: 1, time: '09:00 AM', activity: 'Breakfast', location: 'Test Bistro', address: '1 Long St',
  google_place_id: placeId, verified: Boolean(placeId), estimated_cost: 120, ...extra,
});

const attributions = () => screen.queryAllByText('Google Maps');

beforeEach(() => {
  // PlacePhoto asks the API for a Google photo; there is none here.
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'No photo' }), { status: 404 })));
  window.scrollTo = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('the Google Maps attribution', () => {
  it('follows Google text rules: exact words, never translated', () => {
    render(<PlaceCard place={GOOGLE_PLACE} isSaved={false} onToggleSave={() => {}} />);
    const [attribution] = attributions();
    expect(attribution.textContent).toBe('Google Maps');
    expect(attribution.getAttribute('translate')).toBe('no');
    expect(attribution.className).toContain('gmp-attribution');
  });

  it('is on every place card with Google data, inside the card', () => {
    render(<SavedView places={[GOOGLE_PLACE, { ...GOOGLE_PLACE, google_place_id: 'ChIJzzz999' }]} onToggleSave={() => {}} onDiscover={() => {}} />);
    const cards = screen.getAllByRole('article');
    expect(cards).toHaveLength(2);
    for (const card of cards) expect(within(card).getByText('Google Maps')).toBeTruthy();
  });

  it('is never on Demo data, which shows the Demo badge instead', () => {
    render(<PlaceCard place={DEMO_PLACE} isSaved={false} onToggleSave={() => {}} />);
    expect(attributions()).toHaveLength(0);
    expect(screen.getByText('Demo')).toBeTruthy();
  });

  it('is on each Stop that is a Google place, and not on general activities or Demo Stops', () => {
    render(
      <TripView
        itinerary={plan([
          stop('ChIJabc123def456'),
          stop(null, { time: '11:00 AM', activity: 'Walk', location: 'Sea Point Promenade', address: null }),
        ])}
        mode="saved"
        onBack={() => {}}
        onDelete={() => {}}
      />,
    );
    const stops = screen.getAllByRole('article');
    expect(within(stops[0]).getByText('Google Maps')).toBeTruthy();
    expect(within(stops[1]).queryByText('Google Maps')).toBeNull();
  });

  it('is not on a Demo plan', () => {
    render(<TripView itinerary={{ ...plan([stop('mock_cape-town_1')]), demo: true }} mode="saved" onBack={() => {}} onDelete={() => {}} />);
    expect(attributions()).toHaveLength(0);
  });

  it('credits saved Google places offered on an unsaved Plan', () => {
    render(
      <TripView
        itinerary={plan([stop(null, { address: null })])}
        mode="preview"
        savedHotspots={[GOOGLE_PLACE]}
        onSave={() => {}}
        onRegenerate={() => {}}
        onEditRequest={() => {}}
        onAddStop={() => {}}
      />,
    );
    const panel = screen.getByRole('heading', { name: 'Add from saved' }).closest('section');
    expect(within(panel).getByText('Google Maps')).toBeTruthy();
  });
});
