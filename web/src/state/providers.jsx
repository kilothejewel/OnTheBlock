import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Toast, WakingBanner } from '../components/Feedback';
import { apiFetch } from '../lib/api';
import { useServerWaking } from '../lib/useServerWaking';
import { cityBySlug, rememberCity, storedCity, useCities } from '../lib/cities';
import { PERIODS } from '../lib/places';
import { LibraryContext, PlanningContext, SessionContext, ToastContext, useLibrary, useSession, useToast } from './contexts';

function ToastProvider({ children }) {
  const waking = useServerWaking();
  const [notification, setNotification] = useState(null);
  const timer = useRef(null);

  const notify = useCallback((message, type = 'success') => {
    clearTimeout(timer.current);
    setNotification({ message, type });
    timer.current = setTimeout(() => setNotification(null), 4000);
  }, []);

  // A failed request. 401s are handled by the session (it signs out), and
  // 5xx details are server internals, so those get the friendly fallback.
  const reportError = useCallback((err, fallback) => {
    if (err.status === 401) return;
    notify(err.status >= 500 ? fallback : (err.message || fallback), 'error');
  }, [notify]);

  const value = useMemo(() => ({ notify, reportError }), [notify, reportError]);
  return (
    <ToastContext.Provider value={value}>
      <WakingBanner show={waking} />
      {children}
      <Toast notification={notification} />
    </ToastContext.Provider>
  );
}

function SessionProvider({ initialSession, children }) {
  const { notify } = useToast();
  const [session, setSession] = useState(initialSession);

  const signIn = useCallback((token, username) => {
    try {
      localStorage.setItem('otb_token', token);
      localStorage.setItem('otb_username', username);
    } catch {
      // storage unavailable: signed in for this tab only
    }
    setSession({ token, username });
  }, []);

  const signOut = useCallback(() => {
    try {
      localStorage.removeItem('otb_token');
      localStorage.removeItem('otb_username');
    } catch {
      // nothing stored
    }
    setSession({ token: '', username: '' });
  }, []);

  const { token } = session;
  // Signed-in request. A 401 means the token expired or is invalid, so sign out.
  const api = useCallback(async (path, options = {}) => {
    try {
      return await apiFetch(path, { ...options, token });
    } catch (err) {
      if (err.status === 401 && token) {
        signOut();
        notify('Your session has expired. Please log in again.', 'warning');
      }
      throw err;
    }
  }, [token, signOut, notify]);

  const value = useMemo(
    () => ({ ...session, signedIn: Boolean(session.token), signIn, signOut, api }),
    [session, signIn, signOut, api],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

function LibraryProvider({ children }) {
  const { token, api } = useSession();
  const { notify, reportError } = useToast();
  const [savedHotspots, setSavedHotspots] = useState([]);
  const [savedItineraries, setSavedItineraries] = useState([]);
  // The token the lists were loaded for; they're current when it matches.
  const [loadedFor, setLoadedFor] = useState(null);

  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;
    Promise.all([apiFetch('/hotspots/', { token }), apiFetch('/itineraries/', { token })])
      .then(([hotspots, itineraries]) => {
        if (cancelled) return;
        setSavedHotspots(hotspots);
        setSavedItineraries(itineraries);
        setLoadedFor(token);
      })
      .catch((err) => {
        if (cancelled) return;
        // A 401 here is handled by the next signed-in request.
        if (err.status !== 401) notify("Couldn't load your saved trips and places.", 'warning');
        setLoadedFor(token);
      });
    return () => { cancelled = true; };
  }, [token, notify]);

  const toggleSaveHotspot = useCallback(async (place) => {
    const isSaved = savedHotspots.some((h) => h.google_place_id === place.google_place_id);
    try {
      if (isSaved) {
        await api(`/hotspots/${encodeURIComponent(place.google_place_id)}`, { method: 'DELETE' });
        setSavedHotspots((prev) => prev.filter((h) => h.google_place_id !== place.google_place_id));
        notify('Removed from saved places.', 'info');
      } else {
        const saved = await api('/hotspots/', { method: 'POST', body: place });
        setSavedHotspots((prev) => [...prev, saved]);
        notify(`Saved ${place.name}.`);
      }
    } catch (err) {
      reportError(err, isSaved ? "Couldn't remove that place." : "Couldn't save that place.");
    }
  }, [api, notify, reportError, savedHotspots]);

  const addTrip = useCallback((trip) => setSavedItineraries((prev) => [trip, ...prev]), []);

  const deleteTrip = useCallback(async (id) => {
    try {
      await api(`/itineraries/${id}`, { method: 'DELETE' });
      setSavedItineraries((prev) => prev.filter((i) => i.id !== id));
      notify('Trip deleted.', 'info');
      return true;
    } catch (err) {
      reportError(err, "Couldn't delete this trip. Please try again.");
      return false;
    }
  }, [api, notify, reportError]);

  const signedIn = Boolean(token);
  const value = useMemo(() => ({
    // Nothing is shown from a previous session once signed out.
    savedHotspots: signedIn ? savedHotspots : [],
    savedItineraries: signedIn ? savedItineraries : [],
    loaded: signedIn && loadedFor === token,
    toggleSaveHotspot,
    addTrip,
    deleteTrip,
  }), [signedIn, savedHotspots, savedItineraries, loadedFor, token, toggleSaveHotspot, addTrip, deleteTrip]);
  return <LibraryContext.Provider value={value}>{children}</LibraryContext.Provider>;
}

function PlanningProvider({ children }) {
  const { token, api } = useSession();
  const { addTrip } = useLibrary();
  const { notify, reportError } = useToast();

  // One city for the whole app. A remembered city that's no longer listed
  // (hidden, or removed) falls back to the first one, South Africa first.
  const cities = useCities();
  const [chosenCity, setCity] = useState(storedCity);
  const city = cities.length > 0 && !cityBySlug(cities, chosenCity) ? cities[0].slug : chosenCity;
  // Discover
  const [searchQuery, setSearchQuery] = useState('trendy cafes');
  const [places, setPlaces] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  // A failed search or Plan the user can retry: { message }, shown with a Retry button.
  const [searchError, setSearchError] = useState(null);
  const [planError, setPlanError] = useState(null);
  // Plan form and the unsaved Plan
  const [budget, setBudget] = useState('$$');
  const [duration, setDuration] = useState(1);
  const [preferences, setPreferences] = useState('art, coffee, beach vibes');
  const [previewItinerary, setPreviewItinerary] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [savingTrip, setSavingTrip] = useState(false);

  // Results and the unsaved Plan belong to the session they were made in.
  const [madeFor, setMadeFor] = useState(token);
  if (madeFor !== token) {
    setMadeFor(token);
    if (!token) {
      setPlaces([]);
      setPreviewItinerary(null);
    }
  }

  // Switching city clears results from the old one.
  const changeCity = useCallback((slug) => {
    if (slug === city) return;
    setCity(slug);
    setPlaces([]);
    rememberCity(slug);
  }, [city]);

  const search = useCallback(async () => {
    if (!searchQuery.trim()) return;
    setSearchLoading(true);
    setSearchError(null);
    try {
      setPlaces(await api(`/hotspots/recommend?query=${encodeURIComponent(searchQuery.trim())}&city=${city}`));
    } catch (err) {
      if (err.retryable) setSearchError({ message: err.message || "Couldn't load places. Please try again." });
      else reportError(err, "Couldn't load places. Please try again.");
    } finally {
      setSearchLoading(false);
    }
  }, [api, city, reportError, searchQuery]);

  const generate = useCallback(async () => {
    setGenerating(true);
    setPreviewItinerary(null);
    setPlanError(null);
    window.scrollTo({ top: 0 });
    try {
      /** @type {import('../lib/api').GeneratedPlan} */
      const itinerary = await api('/itineraries/generate', {
        method: 'POST',
        body: { city, budget, duration_days: Number(duration), preferences },
      });
      setPreviewItinerary(itinerary);
    } catch (err) {
      if (err.retryable) setPlanError({ message: err.message || "Couldn't plan that day. Please try again." });
      else reportError(err, "Couldn't plan that day. Please try again.");
    } finally {
      setGenerating(false);
    }
  }, [api, budget, city, duration, preferences, reportError]);

  // Add one of the user's Saved places to the unsaved Plan.
  const addStop = useCallback((place, day, periodId) => {
    const period = PERIODS.find((p) => p.id === periodId) || PERIODS[1];
    setPreviewItinerary((prev) => prev && {
      ...prev,
      items: [
        ...prev.items,
        {
          day,
          time: period.time,
          activity: 'Saved spot',
          location: place.name,
          address: place.address,
          google_place_id: place.google_place_id,
          latitude: place.latitude,
          longitude: place.longitude,
          price_level: place.price_level,
          verified: true,
          description: place.types ? `One of your saved places (${place.types.replace(/_/g, ' ')}).` : 'One of your saved places.',
        },
      ],
    });
    notify(`Added ${place.name} to Day ${day}.`);
  }, [notify]);

  // Saves the unsaved Plan to Trips; resolves to the saved Trip, or null.
  const savePlan = useCallback(async () => {
    if (!previewItinerary || savingTrip) return null;
    setSavingTrip(true);
    try {
      /** @type {import('../lib/api').SavedPlan} */
      const saved = await api('/itineraries/', { method: 'POST', body: previewItinerary });
      addTrip(saved);
      setPreviewItinerary(null);
      notify('Saved to Trips.');
      return saved;
    } catch (err) {
      reportError(err, "Couldn't save this plan. Please try again.");
      return null;
    } finally {
      setSavingTrip(false);
    }
  }, [addTrip, api, notify, previewItinerary, reportError, savingTrip]);

  const value = useMemo(() => ({
    city, changeCity,
    searchQuery, setSearchQuery, places, searchLoading, search, searchError,
    budget, setBudget, duration, setDuration, preferences, setPreferences,
    previewItinerary, clearPreview: () => setPreviewItinerary(null),
    generating, generate, addStop, savingTrip, savePlan, planError,
  }), [
    city, changeCity, searchQuery, places, searchLoading, search, searchError, budget, duration, preferences,
    previewItinerary, generating, generate, addStop, savingTrip, savePlan, planError,
  ]);
  return <PlanningContext.Provider value={value}>{children}</PlanningContext.Provider>;
}

// Every provider, in the order they depend on each other.
export function AppProviders({ initialSession, children }) {
  return (
    <ToastProvider>
      <SessionProvider initialSession={initialSession}>
        <LibraryProvider>
          <PlanningProvider>{children}</PlanningProvider>
        </LibraryProvider>
      </SessionProvider>
    </ToastProvider>
  );
}
