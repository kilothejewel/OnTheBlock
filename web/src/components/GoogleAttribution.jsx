// The "Google Maps" text attribution Google requires wherever content from
// the Places API appears without a Google Map (Places API policies, page of
// 9 Nov 2026): the exact words "Google Maps", on one line, never translated,
// weight 400, 12-16px, grey #5E5E5E (or #1F1F1F / white) at 4.5:1 contrast,
// at the top or bottom of the content it credits and inside its container.
// Styles: .gmp-attribution in index.css. Demo data never shows it.
export default function GoogleAttribution({ className = '' }) {
  return (
    <span className={`gmp-attribution ${className}`.trim()} translate="no" lang="en">
      Google Maps
    </span>
  );
}
