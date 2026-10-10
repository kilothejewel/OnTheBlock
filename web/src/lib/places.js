// Helpers for presenting places and itinerary stops: categories, photos,
// money, time-of-day grouping and Google Maps links.

// Free Unsplash photos (Unsplash License: free to use, no attribution
// required). Loaded straight from Unsplash's CDN, which is how Unsplash asks
// for its images to be used. If a photo can't load, PlacePhoto falls back to
// a category icon tile, so nothing breaks offline.
const UNSPLASH = (id) =>
  `https://images.unsplash.com/photo-${id}?auto=format&fit=crop&w=800&q=70`;

// Warm-lit restaurant terrace used behind the login screen's brand panel.
export const AUTH_PHOTO = UNSPLASH('1726873800099-53f5496281e0').replace('w=800', 'w=1600');

const PHOTOS = {
  cafe: ['1621135177072-57c9b6242e7a', '1601065700897-d9fa1c093f3e'],
  museum: ['1518998053901-5348d3961a04', '1569783721854-33a99b4c0bae'],
  art: ['1530406831759-15c5c0cbce8b', '1540929819775-fcc7d4649250'],
  food: ['1414235077428-338989a2e8c0', '1416453072034-c8dbfa2856b5'],
  nightlife: ['1566417713940-fe7c737a9ef2', '1597075687490-8f673c6c17f6'],
  outdoor: ['1515063312047-b40b86035e20', '1609811876402-241a4e0e5c05'],
  place: ['1726873800099-53f5496281e0', '1648462908676-8305f0eff8e0'],
};

// Order matters: the first rule that matches wins (e.g. "Sunset dinner at
// X Diner & Bar" is food, not nightlife).
const RULES = [
  ['museum', /\b(museum|gallery|galleries|exhibit\w*|art_gallery)\b/],
  ['cafe', /\b(caf[eé]s?|coffee|espresso|bakery|bakeries|breakfast|brunch|tea ?house|pastr\w*)\b/],
  ['food', /\b(dinner|lunch|restaurants?|food|eat\w*|tapas|tacos?|sushi|seafood|diner|bistro|pizza\w*|grill|market|meal_\w+|meal)\b/],
  ['nightlife', /\b(bars?|pubs?|cocktails?|lounge|night ?club|night_club|clubs?|nightlife|rooftop|drinks?|jazz|brewer\w*|wine)\b/],
  ['art', /\b(art|arts|mural\w*|graffiti|street-art|design district|theat(er|re))\b/],
  ['outdoor', /\b(beach\w*|parks?|garden\w*|hik\w*|walk\w*|waterfront|pier|ocean|coast\w*|trail|bay|lake|river|natural_feature|campground)\b/],
];

export function categoryOf(...texts) {
  const hay = texts.filter(Boolean).join(' ').toLowerCase();
  for (const [cat, re] of RULES) if (re.test(hay)) return cat;
  return 'place';
}

export function stopCategory(item) {
  return categoryOf(item.activity, item.location, item.description);
}

export function placeCategory(place) {
  return categoryOf(place.types, place.name);
}

function hash(str = '') {
  let h = 0;
  for (let i = 0; i < str.length; i += 1) h = (h * 31 + str.charCodeAt(i)) | 0;
  return Math.abs(h);
}

export function photoFor(category, seed) {
  const list = PHOTOS[category] || PHOTOS.place;
  return UNSPLASH(list[hash(seed) % list.length]);
}

// The itinerary service prefixes places it couldn't verify.
export function cleanLocation(location = '') {
  return location.replace(/^\[Unverified\]\s*/i, '');
}

export function money(n) {
  if (n === undefined || n === null || Number.isNaN(Number(n))) return null;
  return Number(n) === 0 ? 'Free' : `$${Math.round(Number(n))}`;
}

export function priceLevelLabel(level) {
  return level ? '$'.repeat(level) : null;
}

export function costLabel(item) {
  return money(item.estimated_cost) || priceLevelLabel(item.price_level) || '—';
}

export function sumCost(items) {
  return items.reduce((total, i) => total + (Number(i.estimated_cost) || 0), 0);
}

// "09:00 AM" -> minutes since midnight (unknown -> 9am so it sorts early)
export function minutesOf(time = '') {
  const m = /^(\d{1,2}):(\d{2})\s*(AM|PM)?$/i.exec(time.trim());
  if (!m) return 9 * 60;
  let h = parseInt(m[1], 10) % 12;
  if (m[3] && m[3].toUpperCase() === 'PM') h += 12;
  if (!m[3] && parseInt(m[1], 10) >= 12) h = parseInt(m[1], 10);
  return h * 60 + parseInt(m[2], 10);
}

export const PERIODS = [
  { id: 'Morning', time: '10:00 AM' },
  { id: 'Afternoon', time: '02:00 PM' },
  { id: 'Evening', time: '07:00 PM' },
];

export function periodOf(time) {
  const mins = minutesOf(time);
  if (mins < 12 * 60) return 'Morning';
  if (mins < 17 * 60) return 'Afternoon';
  return 'Evening';
}

// Split an itinerary into days, each grouped into Morning/Afternoon/Evening.
export function buildDays(itinerary) {
  const items = (itinerary?.items || []).map((item, index) => ({ ...item, _key: `${item.day}-${index}` }));
  const maxDay = Math.max(Number(itinerary?.duration_days) || 1, ...items.map((i) => Number(i.day) || 1));
  const days = [];
  for (let d = 1; d <= maxDay; d += 1) {
    const dayItems = items
      .filter((i) => (Number(i.day) || 1) === d)
      .sort((a, b) => minutesOf(a.time) - minutesOf(b.time));
    const groups = PERIODS.map((p) => ({
      name: p.id,
      items: dayItems.filter((i) => periodOf(i.time) === p.id),
    })).filter((g) => g.items.length > 0);
    days.push({ day: d, items: dayItems, groups, total: sumCost(dayItems) });
  }
  return days;
}

export function mapsUrl({ name, address, placeId }) {
  const params = new URLSearchParams({ api: '1' });
  params.set('query', [name, address].filter(Boolean).join(', '));
  if (placeId && !String(placeId).startsWith('mock')) params.set('query_place_id', placeId);
  return `https://www.google.com/maps/search/?${params.toString()}`;
}

export const BUDGET_LABELS = {
  $: 'Budget',
  $$: 'Moderate',
  $$$: 'Premium',
};

export function prettyType(type = '') {
  return type.replace(/_/g, ' ').trim();
}
