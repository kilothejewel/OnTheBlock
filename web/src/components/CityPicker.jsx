import { CITIES } from '../lib/cities';

export default function CityPicker({ value, onChange, labelledBy }) {
  return (
    <div className="chip-row" role="radiogroup" aria-labelledby={labelledBy}>
      {CITIES.map((c) => (
        <button
          key={c.slug}
          type="button"
          role="radio"
          aria-checked={value === c.slug}
          className="chip chip--choice"
          onClick={() => onChange(c.slug)}
        >
          {c.name}
        </button>
      ))}
    </div>
  );
}
