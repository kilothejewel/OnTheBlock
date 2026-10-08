import { useEffect, useState } from 'react';
import { MapPin, Sparkles, LoaderCircle, Check } from 'lucide-react';
import { BUDGET_LABELS } from '../lib/places';

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
        <span className="eyebrow">AI trip planner</span>
        <h1 className="page-title">Plan a trip on your budget</h1>
        <p className="page-lede">Tell us where, how long and how much. We'll build a morning-to-evening plan from real, highly rated places.</p>
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
            : <><Sparkles size={18} aria-hidden="true" /> Build my trip</>}
        </button>
      </form>
    </div>
  );
}

const STEPS = [
  'Finding top-rated places',
  'Matching them to your budget',
  'Arranging your days',
  'Adding the finishing touches',
];

export function GeneratingState({ destination, duration }) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 3500);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="generating" aria-busy="true">
      <section className="page-header" style={{ marginBottom: 0 }}>
        <span className="eyebrow">Building your trip</span>
        <h1 className="page-title">{destination || 'Your trip'}</h1>
        {duration && <p className="page-lede">{duration} {Number(duration) === 1 ? 'day' : 'days'} · this usually takes 10–30 seconds.</p>}
        <ol className="gen-steps" aria-live="polite">
          {STEPS.map((label, i) => (
            <li key={label} className="gen-step" data-state={i < step ? 'done' : i === step ? 'active' : 'todo'}>
              <span className="gen-step__icon" aria-hidden="true">
                {i < step ? <Check size={14} strokeWidth={3} /> : i === step ? <LoaderCircle size={16} className="spinner" /> : null}
              </span>
              {label}{i === step ? '…' : ''}
            </li>
          ))}
        </ol>
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
