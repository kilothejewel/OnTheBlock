import { useCities } from '../lib/cities';

// The cities from GET /cities, South Africa first.
export default function CityPicker({ value, onChange, labelledBy }) {
  const cities = useCities();
  return (
    <div className="chip-row" role="radiogroup" aria-labelledby={labelledBy}>
      {cities.map((c) => (
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
