import { useId, useRef, useState } from 'react';
import { ChevronDown, MapPin } from 'lucide-react';
import { matchCities, useCities } from '../lib/cities';

// The city search box (#89): a WAI-ARIA combobox over GET /cities that matches
// names, provinces and aliases ("Jozi"). With no match it offers to ask for
// the city via `onRequestCity(text)`, which resolves truthy once sent.
export default function CityPicker({ value, onChange, labelledBy, onRequestCity }) {
  const cities = useCities();
  const id = useId();
  const inputRef = useRef(null);
  const listId = `${id}-list`;
  const selected = cities.find((c) => c.slug === value) || null;

  // `text` is what the person has typed; null means "show the chosen city".
  const [text, setText] = useState(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [request, setRequest] = useState({ state: 'idle' }); // idle | sending | sent | error

  const shown = text ?? selected?.name ?? '';
  const query = text ?? '';
  const matches = matchCities(cities, query);
  const noMatch = query.trim() !== '' && matches.length === 0;
  const activeIndex = Math.min(active, Math.max(matches.length - 1, 0));
  const optionId = (i) => `${id}-opt-${i}`;

  function close() {
    setOpen(false);
    setText(null);
    setActive(0);
  }

  function choose(city) {
    close();
    setRequest({ state: 'idle' });
    if (city.slug !== value) onChange(city.slug);
  }

  function onKeyDown(e) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!open) { setOpen(true); return; }
      if (matches.length === 0) return;
      const step = e.key === 'ArrowDown' ? 1 : -1;
      setActive((activeIndex + step + matches.length) % matches.length);
    } else if (e.key === 'Home' && open && matches.length) {
      e.preventDefault();
      setActive(0);
    } else if (e.key === 'End' && open && matches.length) {
      e.preventDefault();
      setActive(matches.length - 1);
    } else if (e.key === 'Enter') {
      if (open && matches[activeIndex]) {
        e.preventDefault();
        choose(matches[activeIndex]);
      } else if (noMatch) {
        e.preventDefault();
      }
    } else if (e.key === 'Escape') {
      if (open || text !== null) {
        e.preventDefault();
        close();
      }
    }
  }

  async function askForCity() {
    if (request.state === 'sending') return;
    const asked = query.trim();
    setRequest({ state: 'sending', text: asked });
    try {
      const sent = await onRequestCity?.(asked);
      setRequest(sent ? { state: 'sent', text: asked } : { state: 'idle' });
    } catch (err) {
      setRequest({ state: 'error', text: asked, message: err?.message || "Couldn't send that. Please try again." });
    }
    // The button is replaced by the answer: keep focus in the picker so it stays open.
    inputRef.current?.focus({ preventScroll: true });
  }

  // Focus moving to something inside the picker (the request button) keeps it open.
  function onBlur(e) {
    if (request.state === 'sending') return;
    if (!e.currentTarget.contains(e.relatedTarget)) close();
  }

  const requestFor = request.text === query.trim() ? request : { state: 'idle' };

  return (
    <div className="city-search" onBlur={onBlur}>
      <div className="city-search__field">
        <MapPin size={18} className="city-search__icon" aria-hidden="true" />
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          className="input city-search__input"
          aria-labelledby={labelledBy}
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && matches[activeIndex] ? optionId(activeIndex) : undefined}
          autoComplete="off"
          spellCheck={false}
          placeholder="Search a city"
          value={shown}
          onChange={(e) => { setText(e.target.value); setOpen(true); setActive(0); }}
          onFocus={(e) => { e.target.select(); setOpen(true); }}
          onClick={() => setOpen(true)}
          onKeyDown={onKeyDown}
        />
        <ChevronDown size={18} className="city-search__chevron" aria-hidden="true" />
      </div>

      <ul id={listId} role="listbox" aria-labelledby={labelledBy} className="city-search__list" hidden={!open || matches.length === 0}>
        {matches.map((city, i) => (
          <li
            key={city.slug}
            id={optionId(i)}
            role="option"
            aria-selected={i === activeIndex}
            data-current={city.slug === value || undefined}
            className="city-search__option"
            onMouseDown={(e) => e.preventDefault()}
            onMouseEnter={() => setActive(i)}
            onClick={() => choose(city)}
          >
            <span className="city-search__name">{city.name}</span>
            <span className="city-search__province">{city.province}</span>
            {city.status === 'beta' && <span className="tag city-search__beta">Beta</span>}
          </li>
        ))}
      </ul>

      <div role="status" aria-live="polite" className="city-search__status">
        {open && noMatch && (
          <div className="city-search__empty">
            {requestFor.state === 'sent' ? (
              <p>Thanks, we&apos;ve noted {requestFor.text}.</p>
            ) : (
              <>
                <p>We don&apos;t cover {query.trim()} yet</p>
                {onRequestCity && (
                  <button type="button" className="btn btn--accent-outline" onClick={askForCity} aria-disabled={requestFor.state === 'sending'}>
                    {requestFor.state === 'sending' ? 'Sending…' : 'Request this city'}
                  </button>
                )}
                {requestFor.state === 'error' && <p className="city-search__error">{requestFor.message}</p>}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
