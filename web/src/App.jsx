import { Navigate, Route, Routes } from 'react-router';
import { loadStoredSession } from './lib/session';
import { AppProviders } from './state/providers';
import AuthPage from './pages/AuthPage';
import Layout, { RequireAuth } from './pages/Layout';
import { DiscoverPage, NotFoundPage, PlanPage, SavedPage, TripPage, TripsPage } from './pages/Pages';

// Every screen has a URL. Discover and the planner are open to everyone; the
// account screens (Trips, Saved) send signed-out visitors to /login and back.
// Each screen's state lives in state/providers.jsx, not here.
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/signup" element={<AuthPage mode="register" />} />
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/discover" replace />} />
        <Route path="discover" element={<DiscoverPage />} />
        <Route path="plan" element={<PlanPage />} />
        <Route path="plan/:city" element={<PlanPage />} />
        <Route element={<RequireAuth />}>
          <Route path="trips" element={<TripsPage />} />
          <Route path="trips/:id" element={<TripPage />} />
          <Route path="saved" element={<SavedPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export default function App({ initialSession = loadStoredSession() }) {
  return (
    <AppProviders initialSession={initialSession}>
      <AppRoutes />
    </AppProviders>
  );
}
