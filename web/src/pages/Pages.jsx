import { useEffect, useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router';
import { MapPinOff } from 'lucide-react';
import DiscoverView from '../components/DiscoverView';
import { EmptyState, RetryPanel } from '../components/Feedback';
import { GeneratingState, PlannerForm } from '../components/PlannerView';
import TripView from '../components/TripView';
import { SavedView, TripsView } from '../components/CollectionViews';
import { cityBySlug, useCities } from '../lib/cities';
import { useLibrary, usePlanning, useSession } from '../state/contexts';
import { useRequireSignIn } from '../state/useRequireSignIn';

// "Request this city" from the city search box (#89). Resolves true once sent.
function useRequestCity() {
  const { api } = useSession();
  const requireSignIn = useRequireSignIn();
  return requireSignIn(async (text) => {
    await api('/city-requests', { method: 'POST', body: { text } });
    return true;
  });
}

export function DiscoverPage() {
  const planning = usePlanning();
  const { savedHotspots, toggleSaveHotspot } = useLibrary();
  const requireSignIn = useRequireSignIn();
  const requestCity = useRequestCity();
  return (
    <DiscoverView
      city={planning.city}
      onCityChange={planning.changeCity}
      onRequestCity={requestCity}
      searchQuery={planning.searchQuery}
      setSearchQuery={planning.setSearchQuery}
      onSearch={requireSignIn((e) => { if (e) e.preventDefault(); planning.search(); })}
      searchLoading={planning.searchLoading}
      searchError={planning.searchError}
      onRetry={() => planning.search()}
      places={planning.places}
      savedHotspots={savedHotspots}
      onToggleSave={requireSignIn(toggleSaveHotspot)}
    />
  );
}

export function PlanPage() {
  const planning = usePlanning();
  const cities = useCities();
  const { savedHotspots } = useLibrary();
  const requireSignIn = useRequireSignIn();
  const requestCity = useRequestCity();
  const navigate = useNavigate();

  // /plan/{city} (#89): choosing a city in the search box opens a new Plan there.
  const { city: cityParam } = useParams();
  const { city, changeCity, clearPreview } = planning;
  const known = cityParam ? cityBySlug(cities, cityParam) : null;
  useEffect(() => {
    if (known && known.slug !== city) {
      changeCity(known.slug);
      clearPreview();
    }
  }, [known, city, changeCity, clearPreview]);

  if (cityParam && cities.length > 0 && !known) return <Navigate to="/plan" replace />;

  if (planning.generating) {
    return <GeneratingState destination={cityBySlug(cities, planning.city)?.name} duration={planning.duration} />;
  }
  if (planning.previewItinerary) {
    return (
      <TripView
        key={planning.previewItinerary.title}
        itinerary={planning.previewItinerary}
        mode="preview"
        savedHotspots={savedHotspots}
        busy={planning.generating || planning.savingTrip}
        onSave={async () => {
          const saved = await planning.savePlan();
          if (saved) navigate(`/trips/${saved.id}`);
        }}
        onRegenerate={() => planning.generate()}
        onEditRequest={() => { planning.clearPreview(); window.scrollTo({ top: 0 }); }}
        onAddStop={planning.addStop}
      />
    );
  }
  return (
    <>
      {planning.planError && (
        <RetryPanel message={planning.planError.message} onRetry={() => planning.generate()} busy={planning.generating} />
      )}
      <PlannerForm
      city={planning.city} onCityChange={(slug) => navigate(`/plan/${slug}`)} onRequestCity={requestCity}
      budget={planning.budget} setBudget={planning.setBudget}
      duration={planning.duration} setDuration={planning.setDuration}
      preferences={planning.preferences} setPreferences={planning.setPreferences}
      onSubmit={requireSignIn((e) => { if (e) e.preventDefault(); planning.generate(); })}
      generating={planning.generating}
      />
    </>
  );
}

export function TripsPage() {
  const { savedItineraries } = useLibrary();
  const navigate = useNavigate();
  return (
    <TripsView
      trips={savedItineraries}
      onOpen={(trip) => navigate(`/trips/${trip.id}`)}
      onPlan={() => navigate('/plan')}
    />
  );
}

function TripNotFound() {
  return (
    <EmptyState icon={MapPinOff} title="Trip not found" action={<Link className="btn btn--primary" to="/trips">Back to Trips</Link>}>
      This Trip doesn't exist, or it belongs to another account.
    </EmptyState>
  );
}

// /trips/:id, opened from Trips or straight from a link.
export function TripPage() {
  const { id } = useParams();
  const { api } = useSession();
  const { savedItineraries, loaded, deleteTrip } = useLibrary();
  const navigate = useNavigate();
  const tripId = /^\d+$/.test(id || '') ? Number(id) : null;
  const known = savedItineraries.find((t) => t.id === tripId);
  // A Trip that isn't in the loaded list yet: { id, trip } once fetched (trip null if not found).
  const [fetched, setFetched] = useState(null);

  useEffect(() => {
    if (tripId === null || known || !loaded) return undefined;
    let cancelled = false;
    api(`/itineraries/${tripId}`)
      .then((trip) => { if (!cancelled) setFetched({ id: tripId, trip }); })
      .catch(() => { if (!cancelled) setFetched({ id: tripId, trip: null }); });
    return () => { cancelled = true; };
  }, [api, known, loaded, tripId]);

  if (tripId === null) return <TripNotFound />;
  const trip = known || (fetched?.id === tripId ? fetched.trip : undefined);
  if (trip === null) return <TripNotFound />;
  if (trip === undefined) return <p className="muted" role="status">Loading your Trip…</p>;

  return (
    <TripView
      key={trip.id}
      itinerary={trip}
      mode="saved"
      onBack={() => navigate('/trips')}
      onDelete={async (tripToDelete) => {
        if (await deleteTrip(tripToDelete)) navigate('/trips', { replace: true });
      }}
    />
  );
}

export function SavedPage() {
  const { savedHotspots, toggleSaveHotspot } = useLibrary();
  const navigate = useNavigate();
  return <SavedView places={savedHotspots} onToggleSave={toggleSaveHotspot} onDiscover={() => navigate('/discover')} />;
}

export function NotFoundPage() {
  return (
    <EmptyState icon={MapPinOff} title="Page not found" action={<Link className="btn btn--primary" to="/discover">Go to Discover</Link>}>
      There's nothing at this address.
    </EmptyState>
  );
}
