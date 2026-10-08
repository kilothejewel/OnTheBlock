import { useState, useEffect, useCallback, useRef } from 'react';
import { TopBar, BottomNav, Footer } from './components/AppShell';
import { Toast } from './components/Feedback';
import AuthScreen from './components/AuthScreen';
import DiscoverView from './components/DiscoverView';
import { PlannerForm, GeneratingState } from './components/PlannerView';
import TripView from './components/TripView';
import { TripsView, SavedView } from './components/CollectionViews';
import { PERIODS } from './lib/places';
import { api, setUnauthorizedHandler, toHotspotPayload, toItineraryPayload } from './lib/api';

const PREVIEW_KEY = 'otb_preview';

// Storage can throw (private mode, blocked cookies); never let that break the app.
const store = {
  get(area, key) { try { return window[area].getItem(key); } catch { return null; } },
  set(area, key, value) { try { window[area].setItem(key, value); } catch { /* ignore */ } },
  remove(area, key) { try { window[area].removeItem(key); } catch { /* ignore */ } },
};

function loadPreview() {
  try { return JSON.parse(store.get('sessionStorage', PREVIEW_KEY)) || null; } catch { return null; }
}

export default function App() {
  // Authentication State
  const [username, setUsername] = useState(() => store.get('localStorage', 'otb_username') || '');
  const [token, setToken] = useState(() => store.get('localStorage', 'otb_token') || '');
  const [authMode, setAuthMode] = useState('login'); // 'login' | 'register'
  const [authForm, setAuthForm] = useState({ identifier: '', email: '', username: '', password: '' });
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState('');

  // Navigation State
  const [activeTab, setActiveTab] = useState('discover'); // 'discover' | 'planner' | 'trips' | 'saved'

  // Discover State
  const [searchQuery, setSearchQuery] = useState('');
  const [places, setPlaces] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [lastQuery, setLastQuery] = useState('');

  // Itinerary Planner State
  const [destination, setDestination] = useState('Miami, FL');
  const [budget, setBudget] = useState('$$');
  const [duration, setDuration] = useState(2);
  const [preferences, setPreferences] = useState('art, coffee, beach');
  const [previewItinerary, setPreviewItinerary] = useState(loadPreview);
  const [generating, setGenerating] = useState(false);
  const [savingTrip, setSavingTrip] = useState(false);

  // Saved Items State
  const [savedHotspots, setSavedHotspots] = useState([]);
  const [savedItineraries, setSavedItineraries] = useState([]);
  const [dataLoading, setDataLoading] = useState(Boolean(token));
  const [viewingItinerary, setViewingItinerary] = useState(null);
  const [pendingPlaceIds, setPendingPlaceIds] = useState(() => new Set());

  // Notification State
  const [notification, setNotification] = useState(null);
  const toastTimer = useRef(null);

  const showNotification = useCallback((message, type = 'success') => {
    clearTimeout(toastTimer.current);
    setNotification({ message, type, id: Date.now() });
    toastTimer.current = setTimeout(() => setNotification(null), type === 'error' ? 6000 : 4000);
  }, []);
  useEffect(() => () => clearTimeout(toastTimer.current), []);

  // Keep an unsaved trip preview across reloads (per tab).
  useEffect(() => {
    if (previewItinerary) store.set('sessionStorage', PREVIEW_KEY, JSON.stringify(previewItinerary));
    else store.remove('sessionStorage', PREVIEW_KEY);
  }, [previewItinerary]);

  const navigate = (tab) => {
    setActiveTab(tab);
    setViewingItinerary(null);
    window.scrollTo({ top: 0 });
  };

  const clearSession = useCallback(() => {
    store.remove('localStorage', 'otb_username');
    store.remove('localStorage', 'otb_token');
    store.remove('sessionStorage', PREVIEW_KEY);
    setUsername('');
    setToken('');
    setPlaces([]);
    setLastQuery('');
    setSearchError('');
    setSavedHotspots([]);
    setSavedItineraries([]);
    setPreviewItinerary(null);
    setViewingItinerary(null);
    setActiveTab('discover');
  }, []);

  // Any authenticated call that comes back 401 means the JWT expired or was
  // revoked: drop the session and send the user back to log in.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearSession();
      setAuthMode('login');
      setAuthError('Your session has expired. Please log in again.');
    });
    return () => setUnauthorizedHandler(null);
  }, [clearSession]);

  // Persist an authenticated session (real JWT from the backend)
  const establishSession = (jwt, name) => {
    store.set('localStorage', 'otb_token', jwt);
    store.set('localStorage', 'otb_username', name);
    setDataLoading(true);
    setToken(jwt);
    setUsername(name);
  };

  // Handle login / registration against the real auth endpoints
  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthError('');

    const isRegister = authMode === 'register';
    const email = authForm.email.trim();
    const newUsername = authForm.username.trim();
    const identifier = authForm.identifier.trim();
    const { password } = authForm;

    if (isRegister && (!email || !newUsername || !password)) {
      setAuthError('Email, username, and password are all required.');
      return;
    }
    if (isRegister && password.length < 8) {
      setAuthError('Password must be at least 8 characters.');
      return;
    }
    if (!isRegister && (!identifier || !password)) {
      setAuthError('Enter your email/username and password.');
      return;
    }

    setAuthLoading(true);
    try {
      const { access_token: jwt } = isRegister
        ? await api.register(email, newUsername, password)
        : await api.login(identifier, password);

      // Resolve the canonical username from the backend (login may use an email).
      let name = isRegister ? newUsername : identifier;
      try {
        const me = await api.me(jwt);
        name = me.username || name;
      } catch {
        // non-fatal: fall back to the value entered
      }

      establishSession(jwt, name);
      setAuthForm({ identifier: '', email: '', username: '', password: '' });
      showNotification(isRegister ? `Welcome to On the Block, ${name}!` : `Welcome back, ${name}!`);
    } catch (err) {
      setAuthError(err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    clearSession();
    showNotification('Logged out.', 'info');
  };

  // Load the user's saved places and trips whenever we have a session.
  // Also validates a token restored from a previous visit (401 -> logged out).
  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;
    Promise.all([api.listHotspots(token), api.listItineraries(token)])
      .then(([hotspots, itineraries]) => {
        if (cancelled) return;
        setSavedHotspots(hotspots || []);
        setSavedItineraries(itineraries || []);
      })
      .catch((err) => {
        if (!cancelled && err.status !== 401) showNotification(`Couldn't load your saved items. ${err.message}`, 'error');
      })
      .finally(() => { if (!cancelled) setDataLoading(false); });
    return () => { cancelled = true; };
  }, [token, showNotification]);

  // Search hotspots (pass a query to search for it directly, e.g. a quick pick)
  const handleSearch = async (e, override) => {
    if (e) e.preventDefault();
    const query = (override ?? searchQuery).trim();
    if (!query) return;
    if (override !== undefined) setSearchQuery(override);
    setSearchLoading(true);
    setSearchError('');
    setLastQuery(query);

    try {
      const data = await api.recommend(token, query);
      setPlaces(data || []);
    } catch (err) {
      if (err.status === 401) return;
      setPlaces([]);
      setSearchError(err.message);
    } finally {
      setSearchLoading(false);
    }
  };

  const setPending = (id, on) => setPendingPlaceIds((prev) => {
    const next = new Set(prev);
    if (on) next.add(id); else next.delete(id);
    return next;
  });

  // Save / unsave a place. Updates optimistically and rolls back on failure.
  const toggleSaveHotspot = async (place) => {
    const id = place.google_place_id;
    if (!id || pendingPlaceIds.has(id)) return;
    const wasSaved = savedHotspots.some((h) => h.google_place_id === id);
    const snapshot = savedHotspots;
    setPending(id, true);

    if (wasSaved) {
      setSavedHotspots((prev) => prev.filter((h) => h.google_place_id !== id));
    } else {
      setSavedHotspots((prev) => [...prev, { ...place, id: `pending-${id}` }]);
    }

    try {
      if (wasSaved) {
        await api.removeHotspot(token, id);
        showNotification(`Removed ${place.name} from saved places.`, 'info');
      } else {
        const saved = await api.saveHotspot(token, toHotspotPayload(place));
        setSavedHotspots((prev) => prev.map((h) => (h.google_place_id === id ? saved : h)));
        showNotification(`Saved ${place.name}.`);
      }
    } catch (err) {
      if (err.status === 401) return;
      setSavedHotspots(snapshot);
      showNotification(`${wasSaved ? "Couldn't remove" : "Couldn't save"} ${place.name}. ${err.message}`, 'error');
    } finally {
      setPending(id, false);
    }
  };

  // Generate Itinerary (also used by "Regenerate", which passes no event)
  const handleGenerateItinerary = async (e) => {
    if (e) e.preventDefault();
    if (!destination.trim() || generating) return;
    const previous = previewItinerary;
    setGenerating(true);
    setPreviewItinerary(null);
    window.scrollTo({ top: 0 });

    try {
      const data = await api.generateItinerary(token, {
        destination: destination.trim(),
        budget,
        duration_days: Number(duration),
        preferences: preferences.trim() || null,
      });
      if (!data || !Array.isArray(data.items) || data.items.length === 0) {
        throw new Error("The planner came back empty. Try different vibes or another city.");
      }
      setPreviewItinerary({ ...data, _generatedAt: Date.now() });
    } catch (err) {
      if (err.status === 401) return;
      // Regenerate failed: keep showing the plan they already had.
      setPreviewItinerary(previous);
      showNotification(`Couldn't build that trip. ${err.message}`, 'error');
    } finally {
      setGenerating(false);
    }
  };

  // Add one of the user's saved places to the unsaved preview
  const handleAddStop = (place, day, periodId) => {
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
    showNotification(`Added ${place.name} to Day ${day}.`);
  };

  const handleSaveItinerary = async () => {
    if (!previewItinerary || savingTrip) return;
    setSavingTrip(true);
    try {
      const saved = await api.saveItinerary(
        token,
        toItineraryPayload(previewItinerary, { destination, budget, duration_days: duration }),
      );
      setSavedItineraries((prev) => [saved, ...prev]);
      setPreviewItinerary(null);
      showNotification('Trip saved.');
      setActiveTab('trips');
      setViewingItinerary(saved);
      window.scrollTo({ top: 0 });
    } catch (err) {
      if (err.status !== 401) showNotification(`Couldn't save your trip. ${err.message}`, 'error');
    } finally {
      setSavingTrip(false);
    }
  };

  const handleDeleteItinerary = async (id) => {
    try {
      await api.deleteItinerary(token, id);
      setSavedItineraries((prev) => prev.filter((i) => i.id !== id));
      setViewingItinerary((v) => (v && v.id === id ? null : v));
      showNotification('Trip deleted.', 'info');
    } catch (err) {
      if (err.status === 404) {
        // Already gone on the server; just drop it locally.
        setSavedItineraries((prev) => prev.filter((i) => i.id !== id));
        setViewingItinerary(null);
        return;
      }
      if (err.status !== 401) showNotification(`Couldn't delete this trip. ${err.message}`, 'error');
      throw err;
    }
  };

  // Login view if not authenticated
  if (!token) {
    return (
      <>
        <AuthScreen
          authMode={authMode}
          onModeChange={(mode) => { setAuthMode(mode); setAuthError(''); }}
          authForm={authForm}
          setAuthForm={setAuthForm}
          authLoading={authLoading}
          authError={authError}
          onSubmit={handleAuthSubmit}
        />
        <Toast notification={notification} />
      </>
    );
  }

  const renderPage = () => {
    switch (activeTab) {
      case 'planner':
        if (generating) return <GeneratingState destination={destination} duration={duration} />;
        if (previewItinerary) {
          return (
            <TripView
              key={previewItinerary._generatedAt || previewItinerary.title}
              itinerary={previewItinerary}
              mode="preview"
              savedHotspots={savedHotspots}
              busy={generating || savingTrip}
              saving={savingTrip}
              onSave={handleSaveItinerary}
              onRegenerate={() => handleGenerateItinerary()}
              onEditRequest={() => { setPreviewItinerary(null); window.scrollTo({ top: 0 }); }}
              onAddStop={handleAddStop}
            />
          );
        }
        return (
          <PlannerForm
            destination={destination} setDestination={setDestination}
            budget={budget} setBudget={setBudget}
            duration={duration} setDuration={setDuration}
            preferences={preferences} setPreferences={setPreferences}
            onSubmit={handleGenerateItinerary}
            generating={generating}
          />
        );
      case 'trips':
        if (viewingItinerary) {
          return (
            <TripView
              key={viewingItinerary.id}
              itinerary={viewingItinerary}
              mode="saved"
              onBack={() => { setViewingItinerary(null); window.scrollTo({ top: 0 }); }}
              onDelete={handleDeleteItinerary}
            />
          );
        }
        return (
          <TripsView
            trips={savedItineraries}
            loading={dataLoading}
            onOpen={(trip) => { setViewingItinerary(trip); window.scrollTo({ top: 0 }); }}
            onPlan={() => navigate('planner')}
          />
        );
      case 'saved':
        return (
          <SavedView
            places={savedHotspots}
            loading={dataLoading}
            pendingIds={pendingPlaceIds}
            onToggleSave={toggleSaveHotspot}
            onDiscover={() => navigate('discover')}
          />
        );
      case 'discover':
      default:
        return (
          <DiscoverView
            username={username}
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            onSearch={handleSearch}
            searchLoading={searchLoading}
            searchError={searchError}
            lastQuery={lastQuery}
            places={places}
            savedHotspots={savedHotspots}
            pendingIds={pendingPlaceIds}
            onToggleSave={toggleSaveHotspot}
            onPlan={() => navigate('planner')}
          />
        );
    }
  };

  return (
    <div className="app">
      <a href="#main" className="skip-link">Skip to content</a>
      <TopBar
        activeTab={activeTab}
        onNavigate={navigate}
        savedCount={savedHotspots.length}
        username={username}
        onLogout={handleLogout}
      />
      <main id="main" className="page" key={activeTab}>
        {renderPage()}
      </main>
      <Footer />
      <BottomNav activeTab={activeTab} onNavigate={navigate} savedCount={savedHotspots.length} />
      <Toast notification={notification} />
    </div>
  );
}
