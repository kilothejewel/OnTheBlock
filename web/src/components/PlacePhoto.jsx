import { useEffect, useState } from 'react';
import { MapPin } from 'lucide-react';
import { photoFor } from '../lib/places';
import { CATEGORY_ICONS } from '../lib/categoryIcons';
import { fetchPlacePhoto, isLivePlaceId } from '../lib/photos';

// A photo slot that always looks finished. In order of preference: an explicit
// `src`, the place's real Google photo (with the photographer credit Google
// requires), a category stock photo, and a category icon if no image loads.
export default function PlacePhoto({ category = 'place', seed = '', src, placeId, alt = '', className = '', iconSize = 40, children }) {
  const wantsLive = !src && isLivePlaceId(placeId);
  // { placeId, photo } once the lookup for that place has answered
  const [live, setLive] = useState(null);
  // Remember which URLs failed, so a new URL gets a fresh attempt.
  const [failedUrls, setFailedUrls] = useState(() => new Set());
  const [loadedUrl, setLoadedUrl] = useState(null);

  useEffect(() => {
    if (!wantsLive) return undefined;
    let active = true;
    fetchPlacePhoto(placeId).then((photo) => {
      if (active) setLive({ placeId, photo });
    });
    return () => { active = false; };
  }, [wantsLive, placeId]);

  const liveAnswered = live?.placeId === placeId;
  const livePhoto = wantsLive && liveAnswered && live.photo?.url && !failedUrls.has(live.photo.url) ? live.photo : null;
  const stockUrl = photoFor(category, seed);
  // While the real photo is being looked up, show the empty tile rather than
  // flashing a stock photo that is about to be replaced.
  const waiting = wantsLive && !liveAnswered;
  const url = src || livePhoto?.url || (waiting ? null : stockUrl);
  const failed = url && failedUrls.has(url);
  const Icon = CATEGORY_ICONS[category] || MapPin;

  return (
    <div className={`photo ${className}`}>
      {failed ? (
        <Icon size={iconSize} strokeWidth={1.5} aria-hidden="true" />
      ) : url && (
        <img
          src={url}
          alt={alt}
          loading="lazy"
          decoding="async"
          data-loaded={loadedUrl === url ? 'true' : 'false'}
          onLoad={() => setLoadedUrl(url)}
          onError={() => setFailedUrls((prev) => new Set(prev).add(url))}
        />
      )}
      {children && <div className="photo__overlay">{children}</div>}
      {livePhoto?.attribution && url === livePhoto.url && (
        livePhoto.attribution_url ? (
          <a className="photo__credit" href={livePhoto.attribution_url} target="_blank" rel="noreferrer">
            Photo: {livePhoto.attribution}
          </a>
        ) : (
          <span className="photo__credit">Photo: {livePhoto.attribution}</span>
        )
      )}
    </div>
  );
}
