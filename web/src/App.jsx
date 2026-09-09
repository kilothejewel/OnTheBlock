import { useState, useEffect, useCallback } from 'react';
import { 
  Compass, 
  Calendar, 
  Heart, 
  Trash2, 
  Sparkles, 
  MapPin, 
  Clock, 
  LogOut, 
  Check, 
  Info,
  ChevronRight,
  ListFilter
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api/v1";

// Helper functions for creating mock data to satisfy linter/compiler purity checks
const createMockSavedHotspot = (place) => ({
  ...place,
  id: Math.floor(Math.random() * 1000),
  created_at: new Date().toISOString()
});

const createMockSavedItinerary = (previewItinerary) => ({
  ...previewItinerary,
  id: Math.floor(Math.random() * 1000),
  user_id: 1,
  created_at: new Date().toISOString()
});

export default function App() {
  // Authentication State
  const [username, setUsername] = useState(localStorage.getItem('otb_username') || '');
  const [token, setToken] = useState(localStorage.getItem('otb_token') || '');
  const [authMode, setAuthMode] = useState('login'); // 'login' | 'register'
  const [authForm, setAuthForm] = useState({ identifier: '', email: '', username: '', password: '' });
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState('');
  
  // Navigation State
  const [activeTab, setActiveTab] = useState('discover'); // 'discover' | 'planner' | 'dashboard'
  
  // Discover State
  const [searchQuery, setSearchQuery] = useState('trendy cafes in Miami');
  const [places, setPlaces] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  
  // Itinerary Planner State
  const [destination, setDestination] = useState('Miami, FL');
  const [budget, setBudget] = useState('$$');
  const [duration, setDuration] = useState(2);
  const [preferences, setPreferences] = useState('art, coffee, beach vibes');
  const [previewItinerary, setPreviewItinerary] = useState(null);
  const [generating, setGenerating] = useState(false);
  
  // Dashboard & Saved Items State
  const [savedHotspots, setSavedHotspots] = useState([]);
  const [savedItineraries, setSavedItineraries] = useState([]);
  const [viewingItinerary, setViewingItinerary] = useState(null);
  
  // Notification State
  const [notification, setNotification] = useState(null);

  const showNotification = (message, type = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 4000);
  };

  // Persist an authenticated session (real JWT from the backend)
  const establishSession = (jwt, name) => {
    localStorage.setItem('otb_token', jwt);
    localStorage.setItem('otb_username', name);
    setToken(jwt);
    setUsername(name);
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
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        setAuthError(data.detail || `Authentication failed (${res.status}).`);
        return;
      }

      const jwt = data.access_token;
      // Resolve the canonical username/profile from the backend.
      let name = isRegister ? payload.username : payload.identifier;
      try {
        const meRes = await fetch(`${API_BASE}/auth/me`, {
          headers: { Authorization: `Bearer ${jwt}` },
        });
        if (meRes.ok) {
          const me = await meRes.json();
          name = me.username || name;
        }
      } catch {
        // non-fatal: fall back to the value entered
      }

      establishSession(jwt, name);
      setAuthForm({ identifier: '', email: '', username: '', password: '' });
      showNotification(
        isRegister ? `Welcome to OnTheBlock, ${name}!` : `Welcome back, ${name}!`,
        'success'
      );
    } catch (err) {
      console.error('Auth error:', err);
      setAuthError('Could not reach the server. Is the API running?');
    } finally {
      setAuthLoading(false);
    }
  };

  // Handle Logout
  const handleLogout = () => {
    localStorage.removeItem('otb_username');
    localStorage.removeItem('otb_token');
    setUsername('');
    setToken('');
    setPlaces([]);
    setSavedHotspots([]);
    setSavedItineraries([]);
    setPreviewItinerary(null);
    setViewingItinerary(null);
    showNotification('Logged out successfully.', 'info');
  };

  // Sync / Fetch user data from backend
  const fetchUserData = useCallback(async () => {
    if (!token) return;
    
    try {
      // 1. Fetch saved hotspots
      const hotspotsRes = await fetch(`${API_BASE}/hotspots/`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (hotspotsRes.ok) {
        const data = await hotspotsRes.json();
        setSavedHotspots(data);
      }
      
      // 2. Fetch saved itineraries
      const itinerariesRes = await fetch(`${API_BASE}/itineraries/`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (itinerariesRes.ok) {
        const data = await itinerariesRes.json();
        setSavedItineraries(data);
      }
    } catch (err) {
      console.error("Error fetching user data:", err);
      showNotification("Could not connect to FastAPI server. Running in mock mode.", "warning");
    }
  }, [token]);

  useEffect(() => {
    fetchUserData();
  }, [fetchUserData]);

  // Search hotspots
  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearchLoading(true);
    
    try {
      const res = await fetch(`${API_BASE}/hotspots/recommend?query=${encodeURIComponent(searchQuery)}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setPlaces(data);
      } else {
        showNotification("Failed to fetch recommendations.", "error");
      }
    } catch (err) {
      console.error(err);
      // Generate client-side fallback if backend is down
      showNotification("FastAPI backend not responding. Using fallback places.", "warning");
      const fallback = [
        { google_place_id: "mock_1", name: "Sunset Diner & Bar", rating: 4.6, address: "Ocean Dr, Miami", price_level: 2, types: "restaurant, bar" },
        { google_place_id: "mock_2", name: "Wynwood Art Coffee", rating: 4.8, address: "NW 2nd Ave, Miami", price_level: 1, types: "cafe, food" }
      ];
      setPlaces(fallback);
    } finally {
      setSearchLoading(false);
    }
  };

  // Save Hotspot
  const toggleSaveHotspot = async (place) => {
    const isSaved = savedHotspots.some(h => h.google_place_id === place.google_place_id);
    
    if (isSaved) {
      // Unsave
      try {
        const res = await fetch(`${API_BASE}/hotspots/${place.google_place_id}`, {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok || res.status === 204) {
          setSavedHotspots(prev => prev.filter(h => h.google_place_id !== place.google_place_id));
          showNotification("Removed from saved hotspots.");
        }
      } catch (err) {
        console.error("Unsave error:", err);
        setSavedHotspots(prev => prev.filter(h => h.google_place_id !== place.google_place_id));
        showNotification("Removed hotspot (offline mode).");
      }
    } else {
      // Save
      try {
        const res = await fetch(`${API_BASE}/hotspots/`, {
          method: 'POST',
          headers: { 
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(place)
        });
        if (res.ok) {
          const newSaved = await res.json();
          setSavedHotspots(prev => [...prev, newSaved]);
          showNotification("Saved to favorites!");
        }
      } catch (err) {
        console.error("Save error:", err);
        const localSaved = createMockSavedHotspot(place);
        setSavedHotspots(prev => [...prev, localSaved]);
        showNotification("Saved to favorites (offline mode)!");
      }
    }
  };

  // Generate Itinerary
  const handleGenerateItinerary = async (e) => {
    e.preventDefault();
    if (!destination.trim()) return;
    setGenerating(true);
    setPreviewItinerary(null);
    
    try {
      const res = await fetch(`${API_BASE}/itineraries/generate`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          destination,
          budget,
          duration_days: parseInt(duration),
          preferences
        })
      });
      if (res.ok) {
        const data = await res.json();
        setPreviewItinerary(data);
      } else {
        showNotification("Generation failed. Please try again.", "error");
      }
    } catch (err) {
      console.error(err);
      showNotification("Generator offline. Displaying template itinerary.", "warning");
      // Rich local fallback
      const mockResult = {
        title: `Weekend Escape in ${destination}`,
        destination,
        budget,
        duration_days: duration,
        items: [
          { day: 1, time: "09:00 AM", activity: "Cozy Breakfast", description: "Grab fresh organic breakfast and a cold brew.", location: "Local Bakery", estimated_cost: 15 },
          { day: 1, time: "02:00 PM", activity: "Sightseeing Walk", description: "Wander through the trendy streets and take in local murals.", location: "Historic Center", estimated_cost: 0 },
          { day: 1, time: "07:00 PM", activity: "Sunset Dinner", description: "Affordable tapas and fresh cocktails near the docks.", location: "The Shore Tavern", estimated_cost: 30 },
          { day: 2, time: "10:00 AM", activity: "Museum Visit", description: "Browse interesting contemporary art exhibits.", location: "Modern Art Institute", estimated_cost: 15 },
          { day: 2, time: "03:00 PM", activity: "Coastal Relaxing", description: "Breathe in the fresh ocean air and dip in the water.", location: "Main Beach", estimated_cost: 0 }
        ]
      };
      setPreviewItinerary(mockResult);
    } finally {
      setGenerating(false);
    }
  };

  // Save Itinerary
  const handleSaveItinerary = async () => {
    if (!previewItinerary) return;
    try {
      const res = await fetch(`${API_BASE}/itineraries/`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(previewItinerary)
      });
      if (res.ok) {
        const saved = await res.json();
        setSavedItineraries(prev => [saved, ...prev]);
        setPreviewItinerary(null);
        showNotification("Itinerary saved to your dashboard!");
        setActiveTab('dashboard');
      }
    } catch (err) {
      console.error("Save itinerary error:", err);
      const localItin = createMockSavedItinerary(previewItinerary);
      setSavedItineraries(prev => [localItin, ...prev]);
      setPreviewItinerary(null);
      showNotification("Itinerary saved locally!");
      setActiveTab('dashboard');
    }
  };

  // Delete Itinerary
  const handleDeleteItinerary = async (id) => {
    try {
      const res = await fetch(`${API_BASE}/itineraries/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok || res.status === 204) {
        setSavedItineraries(prev => prev.filter(i => i.id !== id));
        if (viewingItinerary && viewingItinerary.id === id) {
          setViewingItinerary(null);
        }
        showNotification("Itinerary deleted.");
      }
    } catch (err) {
      console.error("Delete itinerary error:", err);
      setSavedItineraries(prev => prev.filter(i => i.id !== id));
      showNotification("Deleted (offline mode).");
    }
  };

  // Login view if not authenticated
  if (!token) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', padding: '20px' }}>
        <div className="glass-panel" style={{ width: '100%', maxWidth: '450px', padding: '40px', textAlign: 'center', animation: 'fadeIn 0.5s ease' }}>
          <div style={{ display: 'inline-flex', padding: '12px', borderRadius: '50%', background: 'rgba(99, 102, 241, 0.1)', marginBottom: '20px' }}>
            <Compass size={40} color="#6366f1" />
          </div>
          <h1 className="text-gradient-neon" style={{ fontSize: '2.5rem', marginBottom: '10px' }}>OnTheBlock</h1>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '30px' }}>Discover local hotspots and design AI-curated travel itineraries tailored to your budget.</p>

          {/* Login / Register toggle */}
          <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', background: 'rgba(255,255,255,0.03)', padding: '4px', borderRadius: '10px' }}>
            {['login', 'register'].map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => { setAuthMode(mode); setAuthError(''); }}
                style={{
                  flex: 1,
                  padding: '10px',
                  borderRadius: '8px',
                  border: 'none',
                  cursor: 'pointer',
                  fontWeight: '700',
                  textTransform: 'capitalize',
                  background: authMode === mode ? 'rgba(99, 102, 241, 0.25)' : 'transparent',
                  color: authMode === mode ? '#a5b4fc' : 'var(--text-secondary)',
                  transition: 'all 0.2s',
                }}
              >
                {mode === 'login' ? 'Log in' : 'Sign up'}
              </button>
            ))}
          </div>

          <form onSubmit={handleAuthSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px', textAlign: 'left' }}>
            {authMode === 'login' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <label style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-secondary)' }}>Email or username</label>
                <input
                  type="text"
                  autoComplete="username"
                  placeholder="you@example.com"
                  value={authForm.identifier}
                  onChange={(e) => setAuthForm((f) => ({ ...f, identifier: e.target.value }))}
                  required
                  style={{ width: '100%' }}
                />
              </div>
            ) : (
              <>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-secondary)' }}>Email</label>
                  <input
                    type="email"
                    autoComplete="email"
                    placeholder="you@example.com"
                    value={authForm.email}
                    onChange={(e) => setAuthForm((f) => ({ ...f, email: e.target.value }))}
                    required
                    style={{ width: '100%' }}
                  />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-secondary)' }}>Username</label>
                  <input
                    type="text"
                    autoComplete="username"
                    placeholder="At least 3 characters"
                    value={authForm.username}
                    onChange={(e) => setAuthForm((f) => ({ ...f, username: e.target.value }))}
                    required
                    minLength={3}
                    style={{ width: '100%' }}
                  />
                </div>
              </>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-secondary)' }}>Password</label>
              <input
                type="password"
                autoComplete={authMode === 'login' ? 'current-password' : 'new-password'}
                placeholder={authMode === 'login' ? 'Your password' : 'At least 8 characters'}
                value={authForm.password}
                onChange={(e) => setAuthForm((f) => ({ ...f, password: e.target.value }))}
                required
                minLength={authMode === 'login' ? undefined : 8}
                style={{ width: '100%' }}
              />
            </div>

            {authError && (
              <p style={{ fontSize: '0.8rem', color: 'var(--error, #ef4444)', margin: 0 }}>{authError}</p>
            )}

            <button
              type="submit"
              className="btn-primary"
              disabled={authLoading}
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', padding: '14px' }}
            >
              {authLoading
                ? 'Please wait…'
                : (
                  <>
                    {authMode === 'login' ? 'Log in' : 'Create account'} <ChevronRight size={18} />
                  </>
                )}
            </button>
          </form>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '30px', padding: '12px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.03)' }}>
            <Info size={28} color="#14b8a6" />
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'left' }}>
              Accounts are real: the FastAPI backend hashes your password with bcrypt and issues a signed JWT that this app stores locally for API requests.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Toast Notification Banner */}
      {notification && (
        <div style={{
          position: 'fixed',
          top: '20px',
          right: '20px',
          zIndex: 1000,
          background: notification.type === 'error' ? 'var(--error)' : (notification.type === 'warning' ? 'var(--warning)' : '#10b981'),
          color: 'white',
          padding: '12px 24px',
          borderRadius: '8px',
          boxShadow: '0 10px 25px rgba(0,0,0,0.3)',
          fontWeight: '600',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          animation: 'fadeIn 0.2s ease-out'
        }}>
          {notification.message}
        </div>
      )}

      {/* Main Header / Navigation */}
      <header className="glass-panel" style={{ margin: '20px', padding: '15px 30px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderRadius: 'var(--radius-md)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }} onClick={() => setActiveTab('discover')}>
          <Compass size={28} color="#6366f1" />
          <span className="text-gradient-neon" style={{ fontWeight: '800', fontSize: '1.4rem' }}>OnTheBlock</span>
        </div>
        
        {/* Navigation Tabs */}
        <nav style={{ display: 'flex', gap: '8px' }}>
          <button 
            onClick={() => { setActiveTab('discover'); setViewingItinerary(null); }}
            style={{
              background: activeTab === 'discover' ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
              color: activeTab === 'discover' ? '#a5b4fc' : 'var(--text-secondary)',
              border: 'none',
              padding: '8px 16px',
              borderRadius: '8px',
              fontWeight: '600',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.2s'
            }}
          >
            <Compass size={18} /> Discover
          </button>
          
          <button 
            onClick={() => { setActiveTab('planner'); setViewingItinerary(null); }}
            style={{
              background: activeTab === 'planner' ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
              color: activeTab === 'planner' ? '#a5b4fc' : 'var(--text-secondary)',
              border: 'none',
              padding: '8px 16px',
              borderRadius: '8px',
              fontWeight: '600',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.2s'
            }}
          >
            <Sparkles size={18} /> AI Planner
          </button>
          
          <button 
            onClick={() => { setActiveTab('dashboard'); setViewingItinerary(null); }}
            style={{
              background: activeTab === 'dashboard' ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
              color: activeTab === 'dashboard' ? '#a5b4fc' : 'var(--text-secondary)',
              border: 'none',
              padding: '8px 16px',
              borderRadius: '8px',
              fontWeight: '600',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.2s'
            }}
          >
            <Heart size={18} /> Dashboard 
            {(savedHotspots.length > 0 || savedItineraries.length > 0) && (
              <span style={{ fontSize: '0.7rem', background: 'var(--primary)', color: 'white', padding: '1px 6px', borderRadius: '50px' }}>
                {savedHotspots.length + savedItineraries.length}
              </span>
            )}
          </button>
        </nav>

        {/* User Info / Logout */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            User: <strong style={{ color: 'var(--accent)', textTransform: 'capitalize' }}>{username}</strong>
          </span>
          <button 
            onClick={handleLogout}
            style={{
              background: 'transparent',
              border: '1px solid rgba(239, 68, 68, 0.2)',
              color: '#f87171',
              padding: '6px 12px',
              borderRadius: '6px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.8rem',
              fontWeight: '600',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => e.target.style.background = 'rgba(239, 68, 68, 0.08)'}
            onMouseLeave={(e) => e.target.style.background = 'transparent'}
          >
            <LogOut size={14} /> Log out
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main style={{ flex: 1, padding: '0 20px 40px 20px', maxWidth: '1200px', width: '100%', margin: '0 auto', animation: 'fadeIn 0.3s ease' }}>
        
        {/* DISCOVER TAB */}
        {activeTab === 'discover' && (
          <div>
            <div className="glass-panel" style={{ padding: '30px', marginBottom: '30px' }}>
              <h2 style={{ fontSize: '1.8rem', marginBottom: '10px' }} className="text-gradient-primary">Explore Hotspots</h2>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '20px' }}>
                Find local cafes, restaurants, bars, and attractions based on real-time queries.
              </p>
              
              <form onSubmit={handleSearch} style={{ display: 'flex', gap: '10px' }}>
                <input 
                  type="text" 
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="e.g. cocktail bars in Soho New York, beaches in Honolulu..."
                  style={{ flex: 1 }}
                />
                <button type="submit" className="btn-primary" disabled={searchLoading}>
                  {searchLoading ? 'Searching...' : 'Find Places'}
                </button>
              </form>
            </div>

            {/* Recommendations Grid */}
            <div>
              <h3 style={{ fontSize: '1.2rem', color: 'var(--text-secondary)', marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ListFilter size={18} /> Search Results ({places.length})
              </h3>
              
              {places.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '60px 20px', background: 'rgba(255,255,255,0.01)', borderRadius: '12px', border: '1px dashed rgba(255,255,255,0.05)' }}>
                  <Compass size={48} color="var(--text-muted)" style={{ marginBottom: '15px' }} />
                  <p style={{ color: 'var(--text-muted)' }}>Type in a location query above to fetch regional hotspots.</p>
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
                  {places.map((place) => {
                    const isSaved = savedHotspots.some(h => h.google_place_id === place.google_place_id);
                    return (
                      <div key={place.google_place_id} className="glass-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                        <div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                            <h4 style={{ fontSize: '1.1rem' }}>{place.name}</h4>
                            <span className="badge badge-primary" style={{ shrink: 0 }}>
                              {place.price_level ? '$'.repeat(place.price_level) : '$$'}
                            </span>
                          </div>
                          
                          <p style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '10px' }}>
                            <MapPin size={14} color="var(--accent)" /> {place.address}
                          </p>
                          
                          {place.rating && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.85rem', color: '#fbbf24', marginBottom: '15px' }}>
                              <span>★</span> <strong>{place.rating}</strong> <span style={{ color: 'var(--text-muted)' }}>/ 5.0</span>
                            </div>
                          )}
                          
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '20px' }}>
                            {place.types.split(', ').slice(0, 3).map((type) => (
                              <span key={type} style={{ fontSize: '0.7rem', background: 'rgba(255,255,255,0.04)', padding: '2px 8px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                                {type.replace('_', ' ')}
                              </span>
                            ))}
                          </div>
                        </div>

                        <button 
                          onClick={() => toggleSaveHotspot(place)}
                          style={{
                            width: '100%',
                            background: isSaved ? 'rgba(236, 72, 153, 0.1)' : 'rgba(99, 102, 241, 0.1)',
                            border: '1px solid ' + (isSaved ? 'rgba(236, 72, 153, 0.3)' : 'rgba(99, 102, 241, 0.2)'),
                            color: isSaved ? '#fbcfe8' : '#a5b4fc',
                            padding: '10px',
                            borderRadius: '8px',
                            fontWeight: '600',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '6px',
                            transition: 'all 0.2s'
                          }}
                        >
                          {isSaved ? (
                            <>
                              <Check size={16} color="#ec4899" /> Saved to favorites
                            </>
                          ) : (
                            <>
                              <Heart size={16} /> Save to Favorites
                            </>
                          )}
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ITINERARY PLANNER TAB */}
        {activeTab === 'planner' && (
          <div style={{ display: 'grid', gridTemplateColumns: previewItinerary ? '1fr 1fr' : '1fr', gap: '30px', alignItems: 'start' }}>
            {/* Input Config Panel */}
            <div className="glass-panel" style={{ padding: '30px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '15px' }}>
                <Sparkles size={24} color="#ec4899" />
                <h2 style={{ fontSize: '1.8rem' }} className="text-gradient-primary">AI Budget Itinerary</h2>
              </div>
              
              <p style={{ color: 'var(--text-secondary)', marginBottom: '25px' }}>
                Provide travel variables, and our GPT recommendation engine will plan an optimal day-by-day budget timeline.
              </p>
              
              <form onSubmit={handleGenerateItinerary} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-secondary)' }}>Destination City</label>
                  <input 
                    type="text" 
                    value={destination} 
                    onChange={(e) => setDestination(e.target.value)} 
                    placeholder="e.g. Miami, FL" 
                    required 
                  />
                </div>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <label style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-secondary)' }}>Budget Tier</label>
                    <select value={budget} onChange={(e) => setBudget(e.target.value)}>
                      <option value="$">$ (Budget / Backpacker)</option>
                      <option value="$$">$$ (Moderate / Standard)</option>
                      <option value="$$$">$$$ (Luxury / Premium)</option>
                    </select>
                  </div>
                  
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <label style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-secondary)' }}>Duration (Days)</label>
                    <select value={duration} onChange={(e) => setDuration(parseInt(e.target.value))}>
                      <option value={1}>1 Day</option>
                      <option value={2}>2 Days</option>
                      <option value={3}>3 Days</option>
                      <option value={4}>4 Days</option>
                      <option value={5}>5 Days</option>
                    </select>
                  </div>
                </div>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-secondary)' }}>Special Vibes / Preferences</label>
                  <input 
                    type="text" 
                    value={preferences} 
                    onChange={(e) => setPreferences(e.target.value)} 
                    placeholder="e.g. museums, local seafood, beach clubs, architecture" 
                  />
                </div>
                
                <button type="submit" className="btn-primary" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', padding: '14px' }} disabled={generating}>
                  {generating ? (
                    <>Generating with GPT...</>
                  ) : (
                    <>
                      Generate Itinerary <Sparkles size={16} />
                    </>
                  )}
                </button>
              </form>
            </div>

            {/* Generated Preview Panel */}
            {previewItinerary && (
              <div className="glass-panel animate-fade-in" style={{ padding: '30px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
                  <div>
                    <h3 style={{ fontSize: '1.5rem', color: 'var(--text-primary)', marginBottom: '4px' }}>{previewItinerary.title}</h3>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                      Planned for <strong>{previewItinerary.destination}</strong> ({previewItinerary.duration_days} Days)
                    </p>
                  </div>
                  <span className="badge badge-success">{previewItinerary.budget} budget</span>
                </div>

                {/* Timeline */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxHeight: '450px', overflowY: 'auto', paddingRight: '10px', marginBottom: '20px' }}>
                  {previewItinerary.items.map((item, idx) => (
                    <div key={idx} style={{ display: 'flex', gap: '15px', position: 'relative' }}>
                      {/* Day indicator / timeline dot */}
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                        <div style={{ background: 'var(--primary)', color: 'white', fontSize: '0.7rem', fontWeight: '800', width: '38px', height: '24px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          D{item.day}
                        </div>
                        <div style={{ flex: 1, width: '2px', background: 'rgba(255,255,255,0.06)', marginTop: '8px' }}></div>
                      </div>

                      {/* Content block */}
                      <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)', padding: '15px', borderRadius: '8px', flex: 1 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                          <span style={{ fontSize: '0.8rem', color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <Clock size={12} /> {item.time}
                          </span>
                          {item.estimated_cost !== undefined && (
                            <span style={{ fontSize: '0.8rem', color: 'var(--success)', fontWeight: '600' }}>
                              Est. ${item.estimated_cost}
                            </span>
                          )}
                        </div>
                        <h4 style={{ fontSize: '0.95rem', marginBottom: '4px' }}>{item.activity}</h4>
                        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '8px' }}>At {item.location}</p>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{item.description}</p>
                      </div>
                    </div>
                  ))}
                </div>

                <button onClick={handleSaveItinerary} className="btn-primary" style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                  <Heart size={16} /> Save Itinerary to Profile
                </button>
              </div>
            )}
          </div>
        )}

        {/* DASHBOARD TAB */}
        {activeTab === 'dashboard' && (
          <div>
            {/* View specific saved itinerary full details */}
            {viewingItinerary ? (
              <div className="glass-panel" style={{ padding: '30px', animation: 'fadeIn 0.2s ease' }}>
                <button 
                  onClick={() => setViewingItinerary(null)}
                  style={{
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid var(--glass-border)',
                    color: 'var(--text-secondary)',
                    padding: '6px 12px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '0.8rem',
                    marginBottom: '20px'
                  }}
                >
                  ← Back to Dashboard
                </button>
                
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '25px' }}>
                  <div>
                    <h2 style={{ fontSize: '2rem', marginBottom: '6px' }} className="text-gradient-primary">{viewingItinerary.title}</h2>
                    <p style={{ color: 'var(--text-secondary)' }}>
                      Location: <strong>{viewingItinerary.destination}</strong> | Saved on: {new Date(viewingItinerary.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                    <span className="badge badge-primary">{viewingItinerary.budget} budget</span>
                    <button 
                      onClick={() => handleDeleteItinerary(viewingItinerary.id)}
                      style={{
                        background: 'rgba(239, 68, 68, 0.1)',
                        border: '1px solid rgba(239, 68, 68, 0.2)',
                        color: '#f87171',
                        padding: '8px',
                        borderRadius: '6px',
                        cursor: 'pointer'
                      }}
                      title="Delete Itinerary"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {viewingItinerary.items.map((item, idx) => (
                    <div key={idx} style={{ display: 'flex', gap: '15px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                        <div style={{ background: 'var(--primary)', color: 'white', fontSize: '0.75rem', fontWeight: '800', width: '38px', height: '24px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          D{item.day}
                        </div>
                        <div style={{ flex: 1, width: '2px', background: 'rgba(255,255,255,0.06)', marginTop: '8px' }}></div>
                      </div>
                      
                      <div style={{ background: 'rgba(255,255,255,0.01)', border: '1px solid var(--glass-border)', padding: '20px', borderRadius: '10px', flex: 1 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                          <span style={{ fontSize: '0.85rem', color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <Clock size={14} /> {item.time}
                          </span>
                          {item.estimated_cost !== undefined && (
                            <span style={{ fontSize: '0.85rem', color: 'var(--success)', fontWeight: '600' }}>
                              Est. ${item.estimated_cost}
                            </span>
                          )}
                        </div>
                        <h4 style={{ fontSize: '1.05rem', marginBottom: '4px' }}>{item.activity}</h4>
                        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '8px' }}>At {item.location}</p>
                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>{item.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '40px' }}>
                
                {/* Saved Itineraries Section */}
                <div>
                  <h2 style={{ fontSize: '1.8rem', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }} className="text-gradient-primary">
                    <Calendar size={26} color="#6366f1" /> Saved Itineraries ({savedItineraries.length})
                  </h2>
                  
                  {savedItineraries.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '50px 20px', background: 'rgba(255,255,255,0.01)', borderRadius: '12px', border: '1px dashed rgba(255,255,255,0.05)' }}>
                      <Calendar size={40} color="var(--text-muted)" style={{ marginBottom: '10px' }} />
                      <p style={{ color: 'var(--text-muted)', marginBottom: '15px' }}>You haven't saved any travel plans yet.</p>
                      <button onClick={() => setActiveTab('planner')} className="btn-primary" style={{ padding: '10px 20px' }}>
                        Generate One Now
                      </button>
                    </div>
                  ) : (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
                      {savedItineraries.map((itin) => (
                        <div key={itin.id} className="glass-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', cursor: 'pointer' }} onClick={() => setViewingItinerary(itin)}>
                          <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                              <h4 style={{ fontSize: '1.1rem' }}>{itin.title}</h4>
                              <span className="badge badge-primary">{itin.budget}</span>
                            </div>
                            <p style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '15px' }}>
                              <MapPin size={14} color="var(--accent)" /> {itin.destination}
                            </p>
                            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                              Duration: {itin.duration_days} day(s) | Stops: {itin.items.length}
                            </p>
                          </div>

                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '20px', paddingTop: '15px', borderTop: '1px solid rgba(255,255,255,0.05)' }} onClick={(e) => e.stopPropagation()}>
                            <span style={{ fontSize: '0.8rem', color: 'var(--primary)', fontWeight: '600' }} onClick={() => setViewingItinerary(itin)}>
                              View Schedule →
                            </span>
                            <button 
                              onClick={() => handleDeleteItinerary(itin.id)}
                              style={{
                                background: 'transparent',
                                border: 'none',
                                color: '#f87171',
                                cursor: 'pointer',
                                padding: '4px'
                              }}
                              title="Delete Itinerary"
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Saved Hotspots Section */}
                <div>
                  <h2 style={{ fontSize: '1.8rem', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }} className="text-gradient-primary">
                    <Heart size={26} color="#ec4899" /> Favorite Places ({savedHotspots.length})
                  </h2>

                  {savedHotspots.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '50px 20px', background: 'rgba(255,255,255,0.01)', borderRadius: '12px', border: '1px dashed rgba(255,255,255,0.05)' }}>
                      <Heart size={40} color="var(--text-muted)" style={{ marginBottom: '10px' }} />
                      <p style={{ color: 'var(--text-muted)' }}>You haven't saved any hotspots yet. Explore the Discover tab!</p>
                    </div>
                  ) : (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
                      {savedHotspots.map((place) => (
                        <div key={place.google_place_id || place.id} className="glass-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                          <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                              <h4 style={{ fontSize: '1.1rem' }}>{place.name}</h4>
                              <span className="badge badge-secondary">
                                {place.price_level ? '$'.repeat(place.price_level) : '$$'}
                              </span>
                            </div>
                            
                            <p style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '10px' }}>
                              <MapPin size={14} color="var(--accent)" /> {place.address}
                            </p>
                            
                            {place.rating && (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.85rem', color: '#fbbf24', marginBottom: '10px' }}>
                                <span>★</span> <strong>{place.rating}</strong>
                              </div>
                            )}
                          </div>

                          <button 
                            onClick={() => toggleSaveHotspot(place)}
                            style={{
                              marginTop: '15px',
                              width: '100%',
                              background: 'rgba(239, 68, 68, 0.08)',
                              border: '1px solid rgba(239, 68, 68, 0.15)',
                              color: '#f87171',
                              padding: '8px',
                              borderRadius: '6px',
                              fontWeight: '600',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              gap: '6px',
                              fontSize: '0.85rem',
                              transition: 'all 0.2s'
                            }}
                          >
                            <Trash2 size={14} /> Remove Favorite
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

              </div>
            )}
          </div>
        )}

      </main>

      {/* Footer */}
      <footer style={{ padding: '20px', textAlign: 'center', borderTop: '1px solid rgba(255,255,255,0.03)', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
        OnTheBlock © 2026. Made with FastAPI, SQLAlchemy, PostgreSQL, and OpenAI GPT-4o-mini.
      </footer>
    </div>
  );
}
