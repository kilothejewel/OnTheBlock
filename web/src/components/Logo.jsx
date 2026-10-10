// On the Block brand: the "pin block" mark (a map pin drawn as a block with a
// square cut out, so whatever is behind it shows through) and the wordmark.
// Both follow the CSS `color`, which makes light, dark and inverse versions free.

const MARK_PATH =
  'M18.34 9.66a8 8 0 0 1 11.32 0l8.68 8.68a8 8 0 0 1 0 11.32L24 44 9.66 29.66a8 8 0 0 1 0-11.32Z' +
  'M20.5 19h7a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2h-7a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2Z';

export function LogoMark({ className = '' }) {
  return (
    <svg className={`logo-mark ${className}`} viewBox="7 7 34 38" aria-hidden="true" focusable="false">
      <path fill="currentColor" fillRule="evenodd" d={MARK_PATH} />
    </svg>
  );
}

export default function Logo({ className = '' }) {
  return (
    <span className={`logo ${className}`}>
      <LogoMark />
      <span className="logo__text">On the Block</span>
    </span>
  );
}
