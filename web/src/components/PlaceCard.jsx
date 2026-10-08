import { Heart, LoaderCircle, MapPin, Navigation, Star } from 'lucide-react';
import PlacePhoto from './PlacePhoto';
import { mapsUrl, placeCategory, priceLevelLabel, prettyType } from '../lib/places';

export default function PlaceCard({ place, isSaved, pending = false, onToggleSave }) {
  const category = placeCategory(place);
  const types = (place.types || '').split(',').map((t) => t.trim()).filter(Boolean).slice(0, 3);
  const price = priceLevelLabel(place.price_level);

  return (
    <article className="card place-card hover-zoom">
      <PlacePhoto category={category} seed={place.google_place_id || place.name} src={place.photo_url}>
        {price ? <span className="badge">{price}</span> : <span />}
      </PlacePhoto>

      <div className="place-card__body">
        <h3 className="place-card__name">{place.name}</h3>
        {place.address && (
          <p className="place-card__meta">
            <MapPin size={15} aria-hidden="true" style={{ flexShrink: 0 }} /> {place.address}
          </p>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          {place.rating != null && (
            <span className="place-card__rating">
              <Star size={15} fill="currentColor" aria-hidden="true" />
              {place.rating}
              <span className="sr-only"> out of 5</span>
            </span>
          )}
          {types.map((t) => <span key={t} className="tag">{prettyType(t)}</span>)}
        </div>
        <div className="place-card__footer">
          <a
            className="btn btn--outline"
            href={mapsUrl({ name: place.name, address: place.address, placeId: place.google_place_id })}
            target="_blank"
            rel="noreferrer"
          >
            <Navigation size={16} aria-hidden="true" /> Directions
          </a>
          <button
            type="button"
            className={isSaved ? 'btn btn--accent-outline' : 'btn btn--primary'}
            aria-pressed={isSaved}
            aria-busy={pending || undefined}
            disabled={pending}
            aria-label={isSaved ? `Saved. Remove ${place.name} from saved places` : `Save ${place.name}`}
            onClick={() => onToggleSave(place)}
          >
            {pending
              ? <LoaderCircle size={16} className="spinner" aria-hidden="true" />
              : <Heart size={16} aria-hidden="true" fill={isSaved ? 'currentColor' : 'none'} />}
            {isSaved ? 'Saved' : 'Save'}
          </button>
        </div>
      </div>
    </article>
  );
}
