import { Search, LoaderCircle, Compass, Info } from 'lucide-react';
import PlaceCard from './PlaceCard';
import CityPicker from './CityPicker';
import { EmptyState } from './Feedback';
import { cityBySlug } from '../lib/cities';
import { isDemoPlaceId } from '../lib/places';

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

export default function DiscoverView({ city, onCityChange, searchQuery, setSearchQuery, onSearch, searchLoading, places, savedHotspots, onToggleSave }) {
  const savedIds = new Set(savedHotspots.map((h) => h.google_place_id));
  const cityName = cityBySlug(city)?.name;
  const isDemo = places.length > 0 && places.every((p) => isDemoPlaceId(p.google_place_id));

  return (
    <>
      <section className="page-header">
        <span className="eyebrow">Discover</span>
        <h1 className="page-title">What's good on the block?</h1>
        <p className="page-lede">Find cafés, bars, restaurants and things to do in {cityName}. Save the ones you like.</p>
      </section>

      <form className="search-hero" onSubmit={onSearch} role="search">
        <div className="field">
          <span className="field__label" id="discover-city-label">City</span>
          <CityPicker value={city} onChange={onCityChange} labelledBy="discover-city-label" />
        </div>
        <label htmlFor="discover-search" className="sr-only">Search places</label>
        <div className="search-bar">
          <div className="input-group">
            <Search className="input-group__icon" size={20} aria-hidden="true" />
            <input
              id="discover-search"
              className="input"
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="e.g. rooftop bars, brunch, live music"
            />
          </div>
          <button type="submit" className="btn btn--primary btn--lg" disabled={searchLoading || !searchQuery.trim()}>
            {searchLoading ? <LoaderCircle size={18} className="spinner" aria-hidden="true" /> : <Search size={18} aria-hidden="true" />}
            {searchLoading ? 'Searching…' : 'Find places'}
          </button>
        </div>
      </form>

      {searchLoading ? (
        <div className="grid" aria-busy="true">
          {[0, 1, 2].map((i) => <SkeletonCard key={i} />)}
        </div>
      ) : places.length === 0 ? (
        <EmptyState icon={Compass} title="Start with a search">
          Try a type of place in {cityName}, like “brunch spots” or “rooftop bars”.
        </EmptyState>
      ) : (
        <>
          <div className="results-head">
            <h2 className="section-title">Results</h2>
            <span className="muted">{places.length} {places.length === 1 ? 'place' : 'places'}</span>
          </div>
          {isDemo && (
            <p className="demo-note">
              <Info size={16} aria-hidden="true" style={{ flexShrink: 0, marginTop: 2 }} />
              Showing demo places for {cityName}. Live photos, ratings and prices appear when Google Places is connected.
            </p>
          )}
          <div className="grid">
            {places.map((place) => (
              <PlaceCard
                key={place.google_place_id}
                place={place}
                isSaved={savedIds.has(place.google_place_id)}
                onToggleSave={onToggleSave}
              />
            ))}
          </div>
        </>
      )}
    </>
  );
}
