// The cities the app plans in, from the API's registry (GET /cities, which
// lists South African cities first). Fetched once per page load.
import { useEffect, useState } from 'react';
import { apiFetch } from './api';

/** @typedef {{ slug: string, name: string, province: string, country_code: string, currency: string, status: string }} City */

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
