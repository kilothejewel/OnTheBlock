// The cities the app supports. Slugs match the API's (app/core/cities.py).
export const CITIES = [
  { slug: 'miami', name: 'Miami', currency: 'USD' },
  { slug: 'london', name: 'London', currency: 'GBP' },
  { slug: 'cape-town', name: 'Cape Town', currency: 'ZAR' },
  { slug: 'johannesburg', name: 'Johannesburg', currency: 'ZAR' },
  { slug: 'tokyo', name: 'Tokyo', currency: 'JPY' },
];

export const DEFAULT_CITY = 'miami';

export function cityBySlug(slug) {
  return CITIES.find((c) => c.slug === slug) || null;
}

// The last city the person picked, remembered on this device.
export function storedCity() {
  try {
    const slug = localStorage.getItem('otb_city');
    return cityBySlug(slug) ? slug : DEFAULT_CITY;
  } catch {
    return DEFAULT_CITY;
  }
}

export function rememberCity(slug) {
  try {
    localStorage.setItem('otb_city', slug);
  } catch {
    // storage unavailable (private mode): the choice just isn't remembered
  }
}
