import { useState, useEffect, useCallback, useRef } from 'react';
import { TopBar, BottomNav, Footer } from './components/AppShell';
import { Toast } from './components/Feedback';
import AuthScreen from './components/AuthScreen';
import DiscoverView from './components/DiscoverView';
import { PlannerForm, GeneratingState } from './components/PlannerView';
import TripView from './components/TripView';
import { TripsView, SavedView } from './components/CollectionViews';
import { PERIODS } from './lib/places';
import { apiFetch } from './lib/api';
import { cityBySlug, rememberCity, storedCity } from './lib/cities';

const EMPTY_AUTH_FORM = { identifier: '', email: '', username: '', password: '' };

export default function App() {
  // Authentication State
  const [username, setUsername] = useState(localStorage.getItem('otb_username') || '');
  const [token, setToken] = useState(localStorage.getItem('otb_token') || '');
  const [authMode, setAuthMode] = useState('login'); // 'login' | 'register'
  const [authForm, setAuthForm] = useState(EMPTY_AUTH_FORM);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState('');

  // Navigation State
  const [activeTab, setActiveTab] = useState('discover'); // 'discover' | 'planner' | 'trips' | 'saved'

  // Discover State
  const [searchQuery, setSearchQuery] = useState('trendy cafes');
  const [places, setPlaces] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);

  // Itinerary Planner State
  const [city, setCity] = useState(storedCity);
  const [budget, setBudget] = useState('$$');
  const [duration, setDuration] = useState(1);
  const [preferences, setPreferences] = useState('art, coffee, beach vibes');
  const [previewItinerary, setPreviewItinerary] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [savingTrip, setSavingTrip] = useState(false);

  // Saved Items State
  const [savedHotspots, setSavedHotspots] = useState([]);
  const [savedItineraries, setSavedItineraries] = useState([]);
  const [viewingItinerary, setViewingItinerary] = useState(null);

  // Notification State
  const [notification, setNotification] = useState(null);
  const toastTimer = useRef(null);

  const showNotification = useCallback((message, type = 'success') => {
    clearTimeout(toastTimer.current);
    setNotification({ message, type });
    toastTimer.current = setTimeout(() => setNotification(null), 4000);
  }, []);

  const navigate = (tab) => {
    setActiveTab(tab);
    setViewingItinerary(null);
    window.scrollTo({ top: 0 });
  };

  // One city for the whole app; switching clears results from the old city.
  const changeCity = (slug) => {
    if (slug === city) return;
    setCity(slug);
    setPlaces([]);
    rememberCity(slug);
  };

  // Persist an authenticated session (real JWT from the backend)
  const establishSession = (jwt, name) => {
    localStorage.setItem('otb_token', jwt);
    localStorage.setItem('otb_username', name);
    setToken(jwt);
    setUsername(name);
  };

  const clearSession = useCallback(() => {
    localStorage.removeItem('otb_username');
    localStorage.removeItem('otb_token');
    setUsername('');
    setToken('');
    setPlaces([]);
    setSavedHotspots([]);
    setSavedItineraries([]);
    setPreviewItinerary(null);
    setViewingItinerary(null);
    setActiveTab('discover');
  }, []);

  const expireSession = useCallback(() => {
    clearSession();
    showNotification('Your session has expired. Please log in again.', 'warning');
  }, [clearSession, showNotification]);

  // Authenticated request. A 401 means the token expired or is invalid, so sign out.
  const api = async (path, options = {}) => {
    try {
      return await apiFetch(path, { ...options, token });
    } catch (err) {
      if (err.status === 401) expireSession();
      throw err;
    }
  };

  // Show a request failure. 401s were already handled by expireSession, and
  // 5xx details are server internals, so those get the friendly fallback.
  const reportError = (err, fallback) => {
    if (err.status === 401) return;
    const message = err.status >= 500 ? fallback : (err.message || fallback);
    showNotification(message, 'error');
  };

  // Handle login / registration against the real auth endpoints
  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthError('');

    const isRegister = authMode === 'register';
    const endpoint = isRegister ? '/auth/register' : '/auth/login';
    const payload = isRegister
      ? {
          email: authForm.email.trim(),
          username: authForm.username.trim(),
          password: authForm.password,
        }
      : { identifier: authForm.identifier.trim(), password: authForm.password };

    if (isRegister && (!payload.email || !payload.username || !payload.password)) {
      setAuthError('Email, username, and password are all required.');
      return;
    }
    if (!isRegister && (!payload.identifier || !payload.password)) {
      setAuthError('Enter your email/username and password.');
      return;
    }

    setAuthLoading(true);
    try {
      const { access_token: jwt } = await apiFetch(endpoint, { method: 'POST', body: payload });

      // Resolve the canonical username/profile from the backend.
      let name = isRegister ? payload.username : payload.identifier;
      try {
        const me = await apiFetch('/auth/me', { token: jwt });
        name = me.username || name;
      } catch {
        // non-fatal: fall back to the value entered
      }

      establishSession(jwt, name);
      setAuthForm(EMPTY_AUTH_FORM);
      showNotification(
        isRegister ? `Welcome to On the Block, ${name}!` : `Welcome back, ${name}!`,
        'success'
      );
    } catch (err) {
      setAuthError(err.message || 'Please check your details and try again.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    clearSession();
    showNotification('Logged out.', 'info');
  };

  // Load the user's saved places and trips whenever the session changes
  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;

    Promise.all([
      apiFetch('/hotspots/', { token }),
      apiFetch('/itineraries/', { token }),
    ])
      .then(([hotspots, itineraries]) => {
        if (cancelled) return;
        setSavedHotspots(hotspots);
        setSavedItineraries(itineraries);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err.status === 401) expireSession();
        else showNotification("Couldn't load your saved trips and places.", 'warning');
      });

    return () => { cancelled = true; };
  }, [token, expireSession, showNotification]);

  // Search hotspots
  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearchLoading(true);

    try {
      setPlaces(await api(`/hotspots/recommend?query=${encodeURIComponent(searchQuery.trim())}&city=${city}`));
    } catch (err) {
      reportError(err, "Couldn't load places. Please try again.");
    } finally {
      setSearchLoading(false);
    }
  };

  // Save or unsave a hotspot
  const toggleSaveHotspot = async (place) => {
    const isSaved = savedHotspots.some(h => h.google_place_id === place.google_place_id);

    try {
      if (isSaved) {
        await api(`/hotspots/${encodeURIComponent(place.google_place_id)}`, { method: 'DELETE' });
        setSavedHotspots(prev => prev.filter(h => h.google_place_id !== place.google_place_id));
        showNotification('Removed from saved places.', 'info');
      } else {
        const saved = await api('/hotspots/', { method: 'POST', body: place });
        setSavedHotspots(prev => [...prev, saved]);
        showNotification(`Saved ${place.name}.`);
      }
    } catch (err) {
      reportError(err, isSaved ? "Couldn't remove that place." : "Couldn't save that place.");
    }
  };

  // Generate Itinerary (also used by "Regenerate", which passes no event)
  const handleGenerateItinerary = async (e) => {
    if (e) e.preventDefault();
    setGenerating(true);
    setPreviewItinerary(null);
    window.scrollTo({ top: 0 });

    try {
      const itinerary = await api('/itineraries/generate', {
        method: 'POST',
        body: {
          city,
          budget,
          duration_days: Number(duration),
          preferences,
        },
      });
      setPreviewItinerary(itinerary);
    } catch (err) {
      reportError(err, "Couldn't plan that day. Please try again.");
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

  // Save Itinerary
  const handleSaveItinerary = async () => {
    if (!previewItinerary || savingTrip) return;
    setSavingTrip(true);
    try {
      const saved = await api('/itineraries/', { method: 'POST', body: previewItinerary });
      setSavedItineraries(prev => [saved, ...prev]);
      setPreviewItinerary(null);
      showNotification('Saved to Trips.');
      setActiveTab('trips');
      setViewingItinerary(saved);
      window.scrollTo({ top: 0 });
    } catch (err) {
      reportError(err, "Couldn't save this plan. Please try again.");
    } finally {
      setSavingTrip(false);
    }
  };

  // Delete Itinerary
  const handleDeleteItinerary = async (id) => {
    try {
      await api(`/itineraries/${id}`, { method: 'DELETE' });
      setSavedItineraries(prev => prev.filter(i => i.id !== id));
      if (viewingItinerary && viewingItinerary.id === id) {
        setViewingItinerary(null);
      }
      showNotification('Trip deleted.', 'info');
    } catch (err) {
      reportError(err, "Couldn't delete this trip. Please try again.");
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
        if (generating) return <GeneratingState destination={cityBySlug(city)?.name} duration={duration} />;
        if (previewItinerary) {
          return (
            <TripView
              key={previewItinerary.title}
              itinerary={previewItinerary}
              mode="preview"
              savedHotspots={savedHotspots}
              busy={generating || savingTrip}
              onSave={handleSaveItinerary}
              onRegenerate={() => handleGenerateItinerary()}
              onEditRequest={() => { setPreviewItinerary(null); window.scrollTo({ top: 0 }); }}
              onAddStop={handleAddStop}
            />
          );
        }
        return (
          <PlannerForm
            city={city} onCityChange={changeCity}
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
            onOpen={(trip) => { setViewingItinerary(trip); window.scrollTo({ top: 0 }); }}
            onPlan={() => navigate('planner')}
          />
        );
      case 'saved':
        return <SavedView places={savedHotspots} onToggleSave={toggleSaveHotspot} onDiscover={() => navigate('discover')} />;
      case 'discover':
      default:
        return (
          <DiscoverView
            city={city}
            onCityChange={changeCity}
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            onSearch={handleSearch}
            searchLoading={searchLoading}
            places={places}
            savedHotspots={savedHotspots}
            onToggleSave={toggleSaveHotspot}
          />
        );
    }
  };

  return (
    <div className="app">
      <a href="#main" className="sr-only">Skip to content</a>
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
