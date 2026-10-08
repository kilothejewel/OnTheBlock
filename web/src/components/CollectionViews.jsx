import { ArrowRight, CalendarDays, Heart, MapPin, Sparkles, Compass } from 'lucide-react';
import PlacePhoto from './PlacePhoto';
import PlaceCard from './PlaceCard';
import { EmptyState } from './Feedback';
import { SkeletonGrid } from './DiscoverView';
import { BUDGET_LABELS, cleanLocation, money, stopCategory, sumCost } from '../lib/places';

export function TripsView({ trips, loading, onOpen, onPlan }) {
  return (
    <>
      <section className="page-header">
        <span className="eyebrow">Your trips</span>
        <h1 className="page-title">Saved trips</h1>
        <p className="page-lede">Every plan you've saved, ready for the day you go.</p>
      </section>

      {loading && trips.length === 0 ? (
        <SkeletonGrid count={3} />
      ) : trips.length === 0 ? (
        <EmptyState
          icon={CalendarDays}
          title="No trips yet"
          action={(
            <button type="button" className="btn btn--primary btn--lg" onClick={onPlan}>
              <Sparkles size={18} aria-hidden="true" /> Plan a trip
            </button>
          )}
        >
          Build a plan with the AI trip planner and save it here.
        </EmptyState>
      ) : (
        <div className="grid">
          {trips.map((trip) => {
            const items = trip.items || [];
            const first = items[0];
            const total = sumCost(items);
            return (
              <article key={trip.id} className="card trip-card hover-zoom">
                <PlacePhoto
                  category={first ? stopCategory(first) : 'place'}
                  seed={first ? `${cleanLocation(first.location)}-${first.time}` : trip.title}
                  src={first?.photo_url}
                >
                  <span className="badge">{trip.budget} {BUDGET_LABELS[trip.budget] || ''}</span>
                </PlacePhoto>
                <div className="trip-card__body">
                  <h2 className="trip-card__title">
                    <button type="button" className="trip-card__link" onClick={() => onOpen(trip)}>{trip.title}</button>
                  </h2>
                  <span className="trip-card__meta">
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      <MapPin size={14} aria-hidden="true" /> {trip.destination}
                    </span>
                    <span>{trip.duration_days} {Number(trip.duration_days) === 1 ? 'day' : 'days'}</span>
                    <span>{items.length} {items.length === 1 ? 'stop' : 'stops'}</span>
                  </span>
                  <span className="trip-card__foot">
                    <span className="muted">Est. {money(total) || '—'}</span>
                    <span className="trip-card__cta" aria-hidden="true">View trip <ArrowRight size={16} /></span>
                  </span>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </>
  );
}

export function SavedView({ places, loading, pendingIds, onToggleSave, onDiscover }) {
  return (
    <>
      <section className="page-header">
        <span className="eyebrow">Saved</span>
        <h1 className="page-title">Saved places</h1>
        <p className="page-lede">
          {places.length > 0
            ? `${places.length} ${places.length === 1 ? 'place' : 'places'} on your shortlist. Add any of them to a trip from the planner.`
            : 'Your shortlist. Add any of these to a new trip from the planner.'}
        </p>
      </section>

      {loading && places.length === 0 ? (
        <SkeletonGrid count={3} />
      ) : places.length === 0 ? (
        <EmptyState
          icon={Heart}
          title="Nothing saved yet"
          action={(
            <button type="button" className="btn btn--primary btn--lg" onClick={onDiscover}>
              <Compass size={18} aria-hidden="true" /> Discover places
            </button>
          )}
        >
          Tap Save on any place in Discover and it will show up here.
        </EmptyState>
      ) : (
        <div className="grid">
          {places.map((place) => (
            <PlaceCard key={place.google_place_id || place.id} place={place} isSaved pending={pendingIds?.has(place.google_place_id)} onToggleSave={onToggleSave} />
          ))}
        </div>
      )}
    </>
  );
}
