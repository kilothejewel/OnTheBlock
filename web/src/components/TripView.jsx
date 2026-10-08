import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowLeft, BadgeCheck, CalendarDays, Check, ChevronDown, ChevronUp, Heart, LoaderCircle,
  MapPin, Navigation, Pencil, Plus, RefreshCw, Trash2, X,
} from 'lucide-react';
import PlacePhoto from './PlacePhoto';
import { CATEGORY_ICONS } from '../lib/categoryIcons';
import {
  BUDGET_LABELS, PERIODS, buildDays, cleanLocation, costLabel, mapsUrl, money, placeCategory, stopCategory,
} from '../lib/places';

/* ------------------------------------------------------------------ */
/* One stop on the timeline                                            */
/* ------------------------------------------------------------------ */
function StopCard({ item, open, onToggle }) {
  const category = stopCategory(item);
  const Icon = CATEGORY_ICONS[category];
  const location = cleanLocation(item.location);
  const title = location || item.activity;
  const showActivity = location && item.activity && item.activity !== location;
  const detailsId = `stop-details-${item._key}`;

  return (
    <article className="card stop hover-zoom">
      <PlacePhoto category={category} seed={`${title}-${item.time}`} src={item.photo_url} iconSize={44}>
        <span className="time-chip">{item.time}</span>
        {Icon && <span className="icon-chip" aria-hidden="true"><Icon size={16} /></span>}
      </PlacePhoto>

      <div className="stop__body">
        <div className="stop__top">
          <div style={{ minWidth: 0 }}>
            <h3 className="stop__title">{title}</h3>
            {showActivity && <p className="stop__activity">{item.activity}</p>}
          </div>
          <span className="stop__cost" aria-label={`Estimated cost ${costLabel(item)}`}>{costLabel(item)}</span>
        </div>

        {item.address ? (
          <p className="stop__meta">
            <MapPin size={14} aria-hidden="true" style={{ flexShrink: 0 }} />
            <span>{item.address}</span>
            {item.verified && (
              <span className="stop__verified"><BadgeCheck size={14} aria-hidden="true" /> Verified place</span>
            )}
          </p>
        ) : (item.verified === false || /^\[Unverified\]/i.test(item.location || '')) ? (
          <p className="stop__meta">General activity · no fixed address</p>
        ) : null}

        {open && item.description && (
          <p id={detailsId} className="stop__desc">{item.description}</p>
        )}

        <div className="stop__actions">
          {item.description && (
            <button type="button" className="btn btn--outline" aria-expanded={open} aria-controls={open ? detailsId : undefined} onClick={onToggle}>
              {open ? 'Hide details' : 'Details'}
              {open ? <ChevronUp size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}
            </button>
          )}
          <a
            className="btn btn--accent-outline"
            href={mapsUrl({ name: location || item.activity, address: item.address, placeId: item.google_place_id })}
            target="_blank"
            rel="noreferrer"
          >
            <Navigation size={16} aria-hidden="true" /> Directions
          </a>
        </div>
      </div>
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* Add a saved place to the plan                                        */
/* ------------------------------------------------------------------ */
function AddStopSheet({ day, places, initialPlaceId, onAdd, onClose }) {
  const [placeId, setPlaceId] = useState(initialPlaceId || places[0]?.google_place_id || null);
  const [period, setPeriod] = useState('Afternoon');
  const dialogRef = useRef(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onCloseRef.current(); };
    document.addEventListener('keydown', onKey);
    dialogRef.current?.focus();
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, []);

  const chosen = places.find((p) => p.google_place_id === placeId);

  return (
    <div className="scrim" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="sheet" role="dialog" aria-modal="true" aria-labelledby="add-stop-title" tabIndex={-1} ref={dialogRef}>
        <div className="sheet__head">
          <h2 id="add-stop-title" className="sheet__title">Add a stop to Day {day}</h2>
          <button type="button" className="btn btn--ghost btn--icon" aria-label="Close" onClick={onClose}>
            <X size={20} aria-hidden="true" />
          </button>
        </div>

        <div className="sheet__body">
          <div className="field">
            <span className="field__label" id="add-stop-when">When?</span>
            <div className="segmented" role="radiogroup" aria-labelledby="add-stop-when">
              {PERIODS.map((p) => (
                <button key={p.id} type="button" role="radio" aria-checked={period === p.id} className="segmented__option" onClick={() => setPeriod(p.id)}>
                  {p.id}
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <span className="field__label" id="add-stop-which">From your saved places</span>
            <div className="pick-list" role="radiogroup" aria-labelledby="add-stop-which">
              {places.map((p) => (
                <button
                  key={p.google_place_id}
                  type="button"
                  role="radio"
                  aria-checked={placeId === p.google_place_id}
                  className="pick"
                  onClick={() => setPlaceId(p.google_place_id)}
                >
                  <PlacePhoto category={placeCategory(p)} seed={p.google_place_id || p.name} src={p.photo_url} iconSize={22} />
                  <span className="pick__text">
                    <span className="saved-list__name">{p.name}</span>
                    {p.address && <span className="saved-list__sub">{p.address}</span>}
                  </span>
                  <span className="pick__check" aria-hidden="true">{placeId === p.google_place_id && <Check size={14} strokeWidth={3} />}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="sheet__foot">
          <button type="button" className="btn btn--primary btn--lg btn--block" disabled={!chosen} onClick={() => onAdd(chosen, period)}>
            <Plus size={18} aria-hidden="true" /> Add to {period.toLowerCase()}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* The trip screen                                                     */
/* ------------------------------------------------------------------ */
export default function TripView({
  itinerary, mode, savedHotspots = [], busy = false, saving = false,
  onSave, onRegenerate, onEditRequest, onAddStop,
  onBack, onDelete,
}) {
  const isPreview = mode === 'preview';
  const days = useMemo(() => buildDays(itinerary), [itinerary]);
  const [dayIdx, setDayIdx] = useState(0);
  const [openKeys, setOpenKeys] = useState(() => new Set());
  const [sheet, setSheet] = useState(null); // { placeId } when open
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await onDelete(itinerary.id);
    } catch {
      // App shows the error toast; let the user try again.
      setDeleting(false);
    }
  };

  const safeIdx = Math.min(dayIdx, days.length - 1);
  const current = days[safeIdx];
  const tripTotal = days.reduce((t, d) => t + d.total, 0);
  const maxDayTotal = Math.max(1, ...days.map((d) => d.total));
  const stopCount = days.reduce((t, d) => t + d.items.length, 0);
  const canAdd = isPreview && savedHotspots.length > 0;

  const pickDay = (i) => { setDayIdx(i); setOpenKeys(new Set()); };
  const toggle = (key) => setOpenKeys((prev) => {
    const next = new Set(prev);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });

  const dayTabLabel = (d) => `${d.items.length} ${d.items.length === 1 ? 'stop' : 'stops'} · ${money(d.total) || '—'}`;

  const actionsPreview = (
    <>
      <button type="button" className="btn btn--primary btn--lg btn--block" onClick={onSave} disabled={busy}>
        {saving ? <LoaderCircle size={18} className="spinner" aria-hidden="true" /> : <Heart size={18} aria-hidden="true" />}
        {saving ? 'Saving…' : 'Save trip'}
      </button>
      <button type="button" className="btn btn--outline btn--lg btn--block" onClick={onRegenerate} disabled={busy}>
        <RefreshCw size={18} aria-hidden="true" /> Regenerate
      </button>
      <button type="button" className="btn btn--ghost btn--block" onClick={onEditRequest} disabled={busy}>
        <Pencil size={16} aria-hidden="true" /> Change destination or budget
      </button>
    </>
  );

  const deleteBlock = confirmDelete ? (
    <div className="confirm" role="alertdialog" aria-labelledby="confirm-delete-text">
      <p id="confirm-delete-text" style={{ fontWeight: 600 }}>Delete this trip? This can't be undone.</p>
      <div className="confirm__actions">
        <button type="button" className="btn btn--outline" onClick={() => setConfirmDelete(false)} disabled={deleting}>Keep it</button>
        <button type="button" className="btn btn--primary" onClick={handleDelete} disabled={deleting}>
          {deleting && <LoaderCircle size={16} className="spinner" aria-hidden="true" />}
          {deleting ? 'Deleting…' : 'Delete'}
        </button>
      </div>
    </div>
  ) : (
    <button type="button" className="btn btn--danger-ghost btn--block" onClick={() => setConfirmDelete(true)}>
      <Trash2 size={16} aria-hidden="true" /> Delete trip
    </button>
  );

  return (
    <div className={`trip ${isPreview ? 'has-action-bar' : ''}`}>
      <div className="trip__main">
        {!isPreview && (
          <button type="button" className="btn btn--ghost trip__back" onClick={onBack}>
            <ArrowLeft size={18} aria-hidden="true" /> All trips
          </button>
        )}

        <header className="trip__header">
          <span className="eyebrow">{isPreview ? 'Trip preview · not saved yet' : 'Saved trip'}</span>
          <h1 className="page-title">{itinerary.title}</h1>
          <div className="trip__meta">
            <span className="trip__meta-item"><MapPin size={16} aria-hidden="true" /> {itinerary.destination}</span>
            <span aria-hidden="true">·</span>
            <span>{days.length} {days.length === 1 ? 'day' : 'days'}</span>
            <span aria-hidden="true">·</span>
            <span>{stopCount} {stopCount === 1 ? 'stop' : 'stops'}</span>
            <span className="badge">{itinerary.budget} {BUDGET_LABELS[itinerary.budget] || ''}</span>
          </div>
          {!isPreview && itinerary.created_at && (
            <span className="muted" style={{ fontSize: 14 }}>
              <CalendarDays size={14} aria-hidden="true" style={{ verticalAlign: -2, marginRight: 6 }} />
              Saved {new Date(itinerary.created_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}
            </span>
          )}
        </header>

        {/* Budget summary (phones & tablets; desktop shows it in the side panel) */}
        <section className="card budget-card only-narrow" aria-label="Budget">
          <div>
            <div className="budget-card__label">Day {current.day} estimate</div>
            <div className="budget-card__big">{money(current.total) || '—'}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div className="budget-card__label">Whole trip</div>
            <div style={{ fontSize: 16, fontWeight: 700 }}>{money(tripTotal) || '—'}</div>
            <div className="muted" style={{ fontSize: 12 }}>USD per person, approx.</div>
          </div>
        </section>

        {/* Day tabs */}
        {days.length > 1 && (
          <>
            <div className="segmented day-tabs-narrow" role="group" aria-label="Choose a day">
              {days.map((d, i) => (
                <button key={d.day} type="button" className="segmented__option" aria-pressed={i === safeIdx} onClick={() => pickDay(i)}>
                  Day {d.day}
                  <span className="segmented__sub">{dayTabLabel(d)}</span>
                </button>
              ))}
            </div>
            <div className="day-tabs-wide" role="group" aria-label="Choose a day">
              {days.map((d, i) => (
                <button key={d.day} type="button" className="day-tab" aria-pressed={i === safeIdx} onClick={() => pickDay(i)}>
                  <span className="day-tab__label">Day {d.day}</span>
                  <span className="day-tab__sub">{dayTabLabel(d)}</span>
                </button>
              ))}
            </div>
          </>
        )}

        {/* Timeline */}
        <section className="timeline" aria-label={`Day ${current.day} schedule`}>
          {current.groups.length === 0 && (
            <p className="timeline__empty">Nothing planned for this day yet.</p>
          )}
          {current.groups.map((group, gi) => (
            <div key={group.name} className="timeline__group">
              <div className="timeline__rail" aria-hidden="true">
                <div className="timeline__dot" />
                {gi < current.groups.length - 1 && <div className="timeline__line" />}
              </div>
              <div className="timeline__body">
                <h2 className="timeline__label">{group.name}</h2>
                {group.items.map((item) => (
                  <StopCard key={item._key} item={item} open={openKeys.has(item._key)} onToggle={() => toggle(item._key)} />
                ))}
              </div>
            </div>
          ))}
        </section>

        {/* Add next stop (only before saving: saved trips can't be edited yet) */}
        {isPreview && (
          <section className="add-stop">
            <div className="add-stop__rule"><span className="add-stop__label">Add next stop</span></div>
            <button
              type="button"
              className="fab"
              aria-label={`Add a saved place to Day ${current.day}`}
              disabled={!canAdd}
              onClick={() => setSheet({ placeId: null })}
              style={!canAdd ? { opacity: 0.5, cursor: 'not-allowed' } : undefined}
            >
              <Plus size={26} aria-hidden="true" />
            </button>
            <span className="muted" style={{ fontSize: 14, textAlign: 'center' }}>
              {canAdd ? 'Pick from your saved places' : 'Save places in Discover to add them here'}
            </span>
          </section>
        )}

        {!isPreview && <div className="only-narrow">{deleteBlock}</div>}
      </div>

      {/* Desktop side panel */}
      <aside className="trip__aside" aria-label="Trip summary">
        <section className="card card--pad summary">
          <div className="summary__head">
            <h2 className="section-title" style={{ fontSize: 18 }}>Trip budget</h2>
            <span className="badge">{itinerary.budget} {BUDGET_LABELS[itinerary.budget] || ''}</span>
          </div>
          <div>
            <div className="summary__total">{money(tripTotal) || '—'}</div>
            <div className="muted" style={{ fontSize: 13 }}>Estimated, USD per person</div>
          </div>
          {days.length > 1 && (
            <div className="summary__rows">
              {days.map((d) => (
                <div key={d.day} className="summary__row">
                  <div className="summary__row-top">
                    <span style={{ color: 'var(--text-2)' }}>Day {d.day}</span>
                    <span style={{ fontWeight: 700 }}>{money(d.total) || '—'}</span>
                  </div>
                  <div className="bar"><div className="bar__fill" style={{ width: `${Math.round((d.total / maxDayTotal) * 100)}%` }} /></div>
                </div>
              ))}
            </div>
          )}
          <div className="summary__actions">
            {isPreview ? actionsPreview : deleteBlock}
          </div>
        </section>

        {isPreview && savedHotspots.length > 0 && (
          <section className="card card--pad">
            <h2 className="section-title" style={{ fontSize: 18 }}>Add from saved</h2>
            <p className="muted" style={{ fontSize: 14, margin: '4px 0 8px' }}>Drop a favourite into Day {current.day}.</p>
            <div className="saved-list">
              {savedHotspots.slice(0, 5).map((p) => (
                <div key={p.google_place_id} className="saved-list__item">
                  <div className="saved-list__text">
                    <span className="saved-list__name">{p.name}</span>
                    {p.address && <span className="saved-list__sub">{p.address}</span>}
                  </div>
                  <button type="button" className="btn btn--outline" style={{ minHeight: 36, padding: '0 12px', fontSize: 13 }} aria-label={`Add ${p.name}`} onClick={() => setSheet({ placeId: p.google_place_id })}>
                    <Plus size={14} aria-hidden="true" /> Add
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}
      </aside>

      {/* Phone action bar */}
      {isPreview && (
        <div className="action-bar">
          <button type="button" className="btn btn--outline btn--lg btn--icon" aria-label="Regenerate trip" onClick={onRegenerate} disabled={busy}>
            <RefreshCw size={20} aria-hidden="true" />
          </button>
          <button type="button" className="btn btn--outline btn--lg btn--icon" aria-label="Change destination or budget" onClick={onEditRequest} disabled={busy}>
            <Pencil size={18} aria-hidden="true" />
          </button>
          <button type="button" className="btn btn--primary btn--lg" onClick={onSave} disabled={busy}>
            {saving ? <LoaderCircle size={18} className="spinner" aria-hidden="true" /> : <Heart size={18} aria-hidden="true" />}
            {saving ? 'Saving…' : 'Save trip'}
          </button>
        </div>
      )}

      {sheet && (
        <AddStopSheet
          day={current.day}
          places={savedHotspots}
          initialPlaceId={sheet.placeId}
          onClose={() => setSheet(null)}
          onAdd={(place, period) => { onAddStop(place, current.day, period); setSheet(null); }}
        />
      )}
    </div>
  );
}
