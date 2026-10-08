import { Search, LoaderCircle, Compass, MapPin, RefreshCw, Sparkles, WifiOff, ArrowRight } from 'lucide-react';
import PlaceCard from './PlaceCard';
import PlacePhoto from './PlacePhoto';
import { EmptyState } from './Feedback';

// Ready-made searches for the first visit, so the page never opens blank.
const INSPIRATION = [
  { query: 'Trendy cafés in Miami', category: 'cafe', title: 'Coffee & brunch', city: 'Miami' },
  { query: 'Rooftop bars in New York', category: 'nightlife', title: 'Rooftop bars', city: 'New York' },
  { query: 'Street art in Wynwood, Miami', category: 'art', title: 'Street art', city: 'Wynwood' },
  { query: 'Best tacos in Los Angeles', category: 'food', title: 'Late-night eats', city: 'Los Angeles' },
  { query: 'Museums in Chicago', category: 'museum', title: 'Museums', city: 'Chicago' },
  { query: 'Beaches and parks in San Diego', category: 'outdoor', title: 'Sun & parks', city: 'San Diego' },
];

function SkeletonCard() {
  return (
    <div className="card place-card" aria-hidden="true">
      <div className="skeleton" style={{ height: 168, borderRadius: 0 }} />
      <div className="place-card__body">
        <div className="skeleton" style={{ height: 20, width: '70%' }} />
        <div className="skeleton" style={{ height: 14, width: '90%' }} />
        <div className="skeleton" style={{ height: 14, width: '40%' }} />
        <div className="skeleton" style={{ height: 44, marginTop: 12 }} />
      </div>
    </div>
  );
}

export function SkeletonGrid({ count = 3 }) {
  return (
    <div className="grid" aria-busy="true" aria-label="Loading">
      {Array.from({ length: count }, (_, i) => <SkeletonCard key={i} />)}
    </div>
  );
}

export default function DiscoverView({
  username, searchQuery, setSearchQuery, onSearch, searchLoading, searchError, lastQuery,
  places, savedHotspots, pendingIds, onToggleSave, onPlan,
}) {
  const savedIds = new Set(savedHotspots.map((h) => h.google_place_id));
  const hasSearched = Boolean(lastQuery);

  let content;
  if (searchLoading) {
    content = <SkeletonGrid count={6} />;
  } else if (searchError) {
    content = (
      <EmptyState
        icon={WifiOff}
        tone="error"
        title="We couldn't load places"
        action={(
          <button type="button" className="btn btn--primary btn--lg" onClick={() => onSearch(null, lastQuery)}>
            <RefreshCw size={18} aria-hidden="true" /> Try again
          </button>
        )}
      >
        {searchError}
      </EmptyState>
    );
  } else if (!hasSearched) {
    content = (
      <>
        <div className="inspo-head">
          <h2 className="section-title">Need a starting point?</h2>
          <span className="muted">Tap one to search</span>
        </div>
        <div className="inspo">
          {INSPIRATION.map((item) => (
            <button
              key={item.query}
              type="button"
              className="inspo-card"
              onClick={() => onSearch(null, item.query)}
              aria-label={`Search for ${item.query}`}
            >
              <PlacePhoto category={item.category} seed={item.query} iconSize={48} />
              <span className="inspo-card__copy">
                <span className="inspo-card__title">{item.title}</span>
                <span className="inspo-card__sub"><MapPin size={13} aria-hidden="true" /> {item.city}</span>
              </span>
            </button>
          ))}
        </div>
      </>
    );
  } else if (places.length === 0) {
    content = (
      <EmptyState icon={Compass} title="No places found">
        Nothing matched “{lastQuery}”. Try a broader search, like a type of place plus a city.
      </EmptyState>
    );
  } else {
    content = (
      <>
        <div className="results-head">
          <h2 className="section-title">
            Results <span className="results-head__query">for “{lastQuery}”</span>
          </h2>
          <span className="muted">{places.length} {places.length === 1 ? 'place' : 'places'}</span>
        </div>
        <div className="grid">
          {places.map((place) => (
            <PlaceCard
              key={place.google_place_id}
              place={place}
              isSaved={savedIds.has(place.google_place_id)}
              pending={pendingIds?.has(place.google_place_id)}
              onToggleSave={onToggleSave}
            />
          ))}
        </div>
      </>
    );
  }

  return (
    <>
      <section className="page-header">
        <span className="eyebrow">{username ? `Hey ${username}` : 'Discover'}</span>
        <h1 className="page-title">What's good on the block?</h1>
        <p className="page-lede">Search any city for cafés, bars, restaurants and things to do. Save the ones you like.</p>
      </section>

      <form className="search-hero" onSubmit={onSearch} role="search">
        <label htmlFor="discover-search" className="sr-only">Search places</label>
        <div className="search-bar">
          <div className="input-group">
            <Search className="input-group__icon" size={20} aria-hidden="true" />
            <input
              id="discover-search"
              className="input"
              type="search"
              enterKeyHint="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="e.g. cocktail bars in SoHo, New York"
            />
          </div>
          <button type="submit" className="btn btn--primary btn--lg" disabled={searchLoading || !searchQuery.trim()}>
            {searchLoading ? <LoaderCircle size={18} className="spinner" aria-hidden="true" /> : <Search size={18} aria-hidden="true" />}
            {searchLoading ? 'Searching…' : 'Find places'}
          </button>
        </div>
      </form>

      <div aria-live="polite">{content}</div>

      {!searchLoading && (
        <section className="cta-band">
          <div>
            <div className="cta-band__title">Got a city in mind?</div>
            <div className="cta-band__text">Let the AI planner turn it into a day-by-day plan that fits your budget.</div>
          </div>
          <button type="button" className="btn btn--primary btn--lg" onClick={onPlan}>
            <Sparkles size={18} aria-hidden="true" /> Plan a trip <ArrowRight size={18} aria-hidden="true" />
          </button>
        </section>
      )}
    </>
  );
}
