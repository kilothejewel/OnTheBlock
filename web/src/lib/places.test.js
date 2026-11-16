import { describe, expect, it } from 'vitest';
import { buildDays, categoryOf, costLabel, mapsUrl, minutesOf, money, periodOf } from './places';

describe('minutesOf', () => {
  it.each([
    ['09:00 AM', 9 * 60],
    ['12:00 AM', 0],
    ['12:30 PM', 12 * 60 + 30],
    ['07:45 pm', 19 * 60 + 45],
    ['1:05 PM', 13 * 60 + 5],
    ['18:30', 18 * 60 + 30],
    ['  10:15 AM  ', 10 * 60 + 15],
  ])('reads %j as %i minutes after midnight', (time, minutes) => {
    expect(minutesOf(time)).toBe(minutes);
  });

  it.each([['soon'], [''], ['25 o\'clock'], [undefined], [null]])(
    'puts an unknown time (%j) at 9am so it sorts early',
    (time) => {
      expect(minutesOf(time)).toBe(9 * 60);
    },
  );
});

describe('periodOf', () => {
  it.each([
    ['12:00 AM', 'Morning'],
    ['11:59 AM', 'Morning'],
    ['12:00 PM', 'Afternoon'],
    ['04:59 PM', 'Afternoon'],
    ['05:00 PM', 'Evening'],
    ['11:30 PM', 'Evening'],
    ['whenever', 'Morning'],
  ])('puts %j in the %s', (time, period) => {
    expect(periodOf(time)).toBe(period);
  });
});

describe('money', () => {
  it('shows 0 as Free', () => {
    expect(money(0, 'ZAR')).toBe('Free');
    expect(money('0')).toBe('Free');
  });

  it('formats whole amounts in the Plan currency', () => {
    expect(money(25)).toBe('$25');
    expect(money(18, 'GBP')).toBe('£18');
    expect(money(1500, 'JPY')).toBe('¥1,500');
    // Some ICU versions put a (no-break) space after the rand sign.
    expect(money(1500, 'ZAR')).toMatch(/^R\s?1,500$/);
    expect(money(449.6, 'ZAR')).toMatch(/^R\s?450$/);
  });

  it('has no label for a missing or non-numeric amount', () => {
    expect(money(undefined)).toBeNull();
    expect(money(null)).toBeNull();
    expect(money('a lot')).toBeNull();
  });
});

describe('costLabel', () => {
  it('prefers the estimated cost', () => {
    expect(costLabel({ estimated_cost: 0, price_level: 3 }, 'USD')).toBe('Free');
    expect(costLabel({ estimated_cost: 120 }, 'ZAR')).toMatch(/^R\s?120$/);
  });

  it('shows the cost model range (#96)', () => {
    const r = (s) => s.replace(/\s/g, '');
    expect(r(costLabel({ estimated_cost: 220, cost_min: 120, cost_max: 220, cost_basis: 'google_price_level' }, 'ZAR'))).toBe('R120–R220');
    expect(r(costLabel({ estimated_cost: 480, cost_min: 480, cost_max: 480, cost_basis: 'fee_table' }, 'ZAR'))).toBe('R480');
    expect(r(costLabel({ estimated_cost: 120, cost_min: 0, cost_max: 120, cost_basis: 'category_band' }, 'ZAR'))).toBe('UptoR120');
    expect(costLabel({ estimated_cost: 0, cost_min: 0, cost_max: 0, cost_basis: 'default' }, 'ZAR')).toBe('Free');
  });

  it('says when a cost is a rough estimate or not confirmed', () => {
    expect(costLabel({ estimated_cost: 40, cost_min: 20, cost_max: 40, cost_basis: 'beta_estimate' }, 'USD')).toBe('$20–$40 (rough estimate)');
    expect(costLabel({ estimated_cost: 0, cost_min: null, cost_max: null, cost_basis: 'unknown', price_level: 2 }, 'ZAR')).toBe('Price not confirmed');
  });

  it('falls back to the price level, then a dash', () => {
    expect(costLabel({ price_level: 2 }, 'USD')).toBe('$$');
    expect(costLabel({}, 'USD')).toBe('—');
    expect(costLabel({ price_level: 0 }, 'USD')).toBe('—');
  });
});

describe('categoryOf', () => {
  it.each([
    [['Breakfast at Truth Coffee'], 'cafe'],
    [['Zeitz MOCAA', 'museum, tourist_attraction'], 'museum'],
    [['Sunset dinner at The Diner & Bar'], 'food'],
    [['Cocktails on a rooftop'], 'nightlife'],
    [['Walk the Sea Point promenade'], 'outdoor'],
    [['Street-art tour in Woodstock'], 'art'],
    [['Something else entirely'], 'place'],
    [[undefined, null, ''], 'place'],
  ])('puts %j in %s', (texts, category) => {
    expect(categoryOf(...texts)).toBe(category);
  });

  it('matches whole words only', () => {
    expect(categoryOf('barbecue')).toBe('place');
    expect(categoryOf('Barbarossa')).toBe('place');
  });
});

describe('buildDays', () => {
  const plan = {
    duration_days: 2,
    items: [
      { day: 1, time: '07:00 PM', activity: 'Dinner', estimated_cost: 300 },
      { day: 1, time: '09:00 AM', activity: 'Breakfast', estimated_cost: 80 },
      { day: 1, time: '01:00 PM', activity: 'Lunch', estimated_cost: 'n/a' },
      { day: 2, time: '12:30 PM', activity: 'Picnic', estimated_cost: 0 },
    ],
  };

  it('sorts each day by time and groups it by period', () => {
    const [day1] = buildDays(plan);
    expect(day1.items.map((i) => i.activity)).toEqual(['Breakfast', 'Lunch', 'Dinner']);
    expect(day1.groups.map((g) => g.name)).toEqual(['Morning', 'Afternoon', 'Evening']);
    expect(day1.total).toBe(380);
  });

  it('leaves out empty periods and gives each Stop a stable key', () => {
    const [, day2] = buildDays(plan);
    expect(day2.groups).toEqual([{ name: 'Afternoon', items: [expect.objectContaining({ activity: 'Picnic' })] }]);
    expect(day2.items[0]._key).toBe('2-3');
  });

  it('keeps empty days and days beyond duration_days', () => {
    expect(buildDays({ duration_days: 3, items: [] }).map((d) => d.items.length)).toEqual([0, 0, 0]);
    expect(buildDays({ duration_days: 1, items: [{ day: 2, activity: 'Late' }] })).toHaveLength(2);
  });

  it('copes with no Plan at all', () => {
    expect(buildDays(null)).toEqual([{ day: 1, items: [], groups: [], total: 0 }]);
  });
});

describe('mapsUrl', () => {
  it('links a real place by its Google place ID', () => {
    const url = new URL(mapsUrl({ name: 'Test Bistro', address: '1 Long St, Cape Town', placeId: 'ChIJabc123' }));
    expect(url.origin + url.pathname).toBe('https://www.google.com/maps/search/');
    expect(url.searchParams.get('api')).toBe('1');
    expect(url.searchParams.get('query')).toBe('Test Bistro, 1 Long St, Cape Town');
    expect(url.searchParams.get('query_place_id')).toBe('ChIJabc123');
  });

  it('never sends a Demo place ID to Google', () => {
    const url = new URL(mapsUrl({ name: 'Demo Cafe', placeId: 'mock_cape-town_1' }));
    expect(url.searchParams.get('query')).toBe('Demo Cafe');
    expect(url.searchParams.has('query_place_id')).toBe(false);
  });
});
