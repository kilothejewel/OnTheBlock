// The cities the app plans in, from the API's registry (GET /cities, which
// lists South African cities first). Fetched once per page load.
import { useEffect, useState } from 'react';
import { apiFetch } from './api';

/** @typedef {{ slug: string, name: string, province: string, country_code: string, currency: string, status: string, aliases?: string[] }} City */

export const DEFAULT_CITY = 'cape-town';

/** @type {Promise<City[]> | null} */
let request = null;
/** @type {City[] | null} */
let loaded = null;

// The visible cities. Resolves to [] if the API can't be reached; a later call tries again.
export function loadCities() {
  if (!request) {
    request = apiFetch('/cities')
      .then((cities) => {
        loaded = cities;
        return cities;
      })
      .catch(() => {
        request = null;
        return [];
      });
  }
  return request;
}

// For tests: forget the fetched list.
export function resetCities() {
  request = null;
  loaded = null;
}

// The cities, [] until they've loaded.
export function useCities() {
  const [cities, setCities] = useState(() => loaded || []);
  useEffect(() => {
    if (loaded) return undefined;
    let cancelled = false;
    loadCities().then((list) => { if (!cancelled) setCities(list); });
    return () => { cancelled = true; };
  }, []);
  return cities;
}

// Lower case without accents, so "Joburg", "joburg" and "jöburg" all match.
function fold(text) {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}

// The cities whose name, province or an alias contains `query`, names that
// start with it first. An empty query lists every city in the API's order.
export function matchCities(cities, query) {
  const q = fold(query || '');
  if (!q) return cities;
  const scored = [];
  cities.forEach((city, index) => {
    const names = [city.name, ...(city.aliases || [])].map(fold);
    let score = null;
    if (names.some((n) => n.startsWith(q))) score = 0;
    else if (names.some((n) => n.split(/[\s-]+/).some((w) => w.startsWith(q)))) score = 1;
    else if (names.some((n) => n.includes(q))) score = 2;
    else if (fold(city.province).includes(q)) score = 3;
    if (score !== null) scored.push({ city, score, index });
  });
  return scored.sort((a, b) => a.score - b.score || a.index - b.index).map((s) => s.city);
}

export function cityBySlug(cities, slug) {
  return cities.find((c) => c.slug === slug) || null;
}

// The last city the person picked, remembered on this device.
export function storedCity() {
  try {
    return localStorage.getItem('otb_city') || DEFAULT_CITY;
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
