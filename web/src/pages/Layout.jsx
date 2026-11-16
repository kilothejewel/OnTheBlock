import { useEffect } from 'react';
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router';
import { BottomNav, Footer, TopBar } from '../components/AppShell';
import { useLibrary, useSession, useToast } from '../state/contexts';

// The tab a path belongs to: /trips/12 is the Trips tab.
function tabOf(pathname) {
  return pathname.split('/')[1] || 'discover';
}

// Account screens (Trips, Saved): signed-out visitors log in first, then come back.
export function RequireAuth() {
  const { signedIn } = useSession();
  const location = useLocation();
  if (!signedIn) return <Navigate to="/login" replace state={{ from: location }} />;
  return <Outlet />;
}

// The top bar, page and bottom nav around every screen except sign-in.
export default function Layout() {
  const { username, signedIn, signOut } = useSession();
  const { savedHotspots } = useLibrary();
  const { notify } = useToast();
  const location = useLocation();
  const navigate = useNavigate();
  const tab = tabOf(location.pathname);

  // Each new screen starts at the top, as the tabs did.
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  const handleLogout = () => {
    signOut();
    notify('Logged out.', 'info');
    navigate('/discover');
  };

  return (
    <div className="app">
      <a href="#main" className="sr-only">Skip to content</a>
      <TopBar
        activeTab={tab}
        onNavigate={(path) => navigate(path)}
        savedCount={savedHotspots.length}
        username={signedIn ? username : ''}
        onLogout={handleLogout}
        onLogin={() => navigate('/login', { state: { from: location } })}
      />
      <main id="main" className="page" key={tab}>
        <Outlet />
      </main>
      <Footer />
      <BottomNav activeTab={tab} onNavigate={(path) => navigate(path)} savedCount={savedHotspots.length} />
    </div>
  );
}
