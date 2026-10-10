import { MapPin, Sparkles, LoaderCircle } from 'lucide-react';
import { BUDGET_LABELS } from '../lib/places';
import { LogoMark } from './Logo';

const VIBES = ['art', 'coffee', 'food', 'nightlife', 'beach', 'museums', 'shopping', 'live music'];

function splitPrefs(value) {
  return value.split(',').map((s) => s.trim()).filter(Boolean);
}

export function PlannerForm({ destination, setDestination, budget, setBudget, duration, setDuration, preferences, setPreferences, onSubmit, generating }) {
  const prefs = splitPrefs(preferences);
  const hasVibe = (v) => prefs.some((p) => p.toLowerCase() === v);
  const toggleVibe = (v) => {
    const next = hasVibe(v) ? prefs.filter((p) => p.toLowerCase() !== v) : [...prefs, v];
    setPreferences(next.join(', '));
  };

  return (
    <div className="planner">
      <section className="page-header">
        <span className="eyebrow">Day planner</span>
        <h1 className="page-title">Plan a day out on your budget</h1>
        <p className="page-lede">Pick a city and what you want to spend. We'll plan your day from morning to evening using real, highly rated places.</p>
      </section>

      <form className="card card--pad planner__form" onSubmit={onSubmit}>
        <div className="field">
          <label className="field__label" htmlFor="plan-destination">Where to?</label>
          <div className="input-group">
            <MapPin className="input-group__icon" size={20} aria-hidden="true" />
            <input
              id="plan-destination"
              className="input"
              type="text"
              value={destination}
              onChange={(e) => setDestination(e.target.value)}
              placeholder="City, e.g. Miami, FL"
              required
            />
          </div>
        </div>

        <div className="planner__row">
          <div className="field">
            <span className="field__label" id="plan-budget-label">Budget</span>
            <div className="segmented" role="radiogroup" aria-labelledby="plan-budget-label">
              {Object.entries(BUDGET_LABELS).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={budget === value}
                  className="segmented__option"
                  onClick={() => setBudget(value)}
                >
                  {value}
                  <span className="segmented__sub">{label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <span className="field__label" id="plan-duration-label">How many days?</span>
            <div className="segmented" role="radiogroup" aria-labelledby="plan-duration-label">
              {[1, 2, 3, 4, 5].map((d) => (
                <button
                  key={d}
                  type="button"
                  role="radio"
                  aria-checked={Number(duration) === d}
                  aria-label={`${d} ${d === 1 ? 'day' : 'days'}`}
                  className="segmented__option"
                  onClick={() => setDuration(d)}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="field">
          <label className="field__label" htmlFor="plan-prefs">What are you into?</label>
          <div className="chip-row" aria-label="Quick picks">
            {VIBES.map((v) => (
              <button key={v} type="button" className="chip" aria-pressed={hasVibe(v)} onClick={() => toggleVibe(v)}>
                {v}
              </button>
            ))}
          </div>
          <input
            id="plan-prefs"
            className="input"
            type="text"
            value={preferences}
            onChange={(e) => setPreferences(e.target.value)}
            placeholder="Or type your own, e.g. vegan food, jazz bars, architecture"
          />
        </div>

        <button type="submit" className="btn btn--primary btn--lg btn--block" disabled={generating || !destination.trim()}>
          {generating
            ? <><LoaderCircle size={18} className="spinner" aria-hidden="true" /> Building your plan…</>
            : <><Sparkles size={18} aria-hidden="true" /> Plan my {Number(duration) === 1 ? 'day' : `${duration} days`}</>}
        </button>
      </form>
    </div>
  );
}

export function GeneratingState({ destination, duration }) {
  return (
    <div className="generating" aria-busy="true" aria-live="polite">
      <section className="page-header" style={{ marginBottom: 0 }}>
        <span className="eyebrow">{Number(duration) > 1 ? 'Planning your days' : 'Planning your day'}</span>
        <h1 className="page-title">{destination || 'Your day'}</h1>
        <p className="generating__status">
          <LogoMark className="logo-mark--pulse" />
          Finding top-rated places and fitting them to your budget…
        </p>
      </section>
      {[0, 1, 2].map((i) => (
        <div key={i} className="timeline__group">
          <div className="timeline__rail">
            <div className="timeline__dot" />
            {i < 2 && <div className="timeline__line" />}
          </div>
          <div className="timeline__body">
            <div className="skeleton" style={{ height: 16, width: 96 }} />
            <div className="card" style={{ overflow: 'hidden' }}>
              <div className="skeleton" style={{ height: 128, borderRadius: 0 }} />
              <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div className="skeleton" style={{ height: 20, width: '60%' }} />
                <div className="skeleton" style={{ height: 14, width: '40%' }} />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
