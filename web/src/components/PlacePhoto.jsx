import { useState } from 'react';
import { MapPin } from 'lucide-react';
import { CATEGORY_ICONS } from '../lib/categoryIcons';
import { photoFor } from '../lib/places';

// A photo slot that always looks finished: shows the place's own photo when
// one is provided, otherwise a category stock photo. While the photo loads,
// or if it can't load (offline, blocked, 404), a category-tinted art tile
// with the category icon shows instead.
export default function PlacePhoto({ category = 'place', seed = '', src, alt = '', className = '', iconSize = 40, children }) {
  const url = src || photoFor(category, seed);
  // Remember which URL failed, so a new URL gets a fresh attempt.
  const [failedUrl, setFailedUrl] = useState(null);
  const [loadedUrl, setLoadedUrl] = useState(null);
  const Icon = CATEGORY_ICONS[category] || MapPin;
  const failed = failedUrl === url;

  return (
    <div className={`photo photo--${category} ${className}`}>
      <span className="photo__art" aria-hidden="true">
        <Icon size={iconSize} strokeWidth={1.5} />
      </span>
      {!failed && (
        <img
          src={url}
          alt={alt}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          data-loaded={loadedUrl === url ? 'true' : 'false'}
          onLoad={() => setLoadedUrl(url)}
          onError={() => setFailedUrl(url)}
        />
      )}
      {children && <div className="photo__overlay">{children}</div>}
    </div>
  );
}
