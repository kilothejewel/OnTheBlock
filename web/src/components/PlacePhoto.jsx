import { useState } from 'react';
import { MapPin } from 'lucide-react';
import { photoFor } from '../lib/places';
import { CATEGORY_ICONS } from '../lib/categoryIcons';

// A photo slot that always looks finished: shows the place's own photo when
// one is provided, otherwise a category stock photo, and falls back to a
// category icon tile if the image can't load (offline, blocked, 404).
export default function PlacePhoto({ category = 'place', seed = '', src, alt = '', className = '', iconSize = 40, children }) {
  const url = src || photoFor(category, seed);
  // Remember which URL failed, so a new URL gets a fresh attempt.
  const [failedUrl, setFailedUrl] = useState(null);
  const [loadedUrl, setLoadedUrl] = useState(null);
  const Icon = CATEGORY_ICONS[category] || MapPin;
  const failed = failedUrl === url;

  return (
    <div className={`photo ${className}`}>
      {failed ? (
        <Icon size={iconSize} strokeWidth={1.5} aria-hidden="true" />
      ) : (
        <img
          src={url}
          alt={alt}
          loading="lazy"
          decoding="async"
          data-loaded={loadedUrl === url ? 'true' : 'false'}
          onLoad={() => setLoadedUrl(url)}
          onError={() => setFailedUrl(url)}
        />
      )}
      {children && <div className="photo__overlay">{children}</div>}
    </div>
  );
}
