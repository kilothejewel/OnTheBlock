import { useEffect, useRef, useState } from 'react';
import { Compass, Sparkles, CalendarDays, Heart, LogIn, LogOut } from 'lucide-react';
import Logo from './Logo';

// id is the first part of the tab's path (/trips/12 is the Trips tab).
const TABS = [
  { id: 'discover', path: '/discover', label: 'Discover', Icon: Compass },
  { id: 'plan', path: '/plan', label: 'Plan', Icon: Sparkles },
  { id: 'trips', path: '/trips', label: 'Trips', Icon: CalendarDays },
  { id: 'saved', path: '/saved', label: 'Saved', Icon: Heart },
];

function AccountMenu({ username, onLogout }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div className="account" ref={ref}>
      <button
        type="button"
        className="avatar"
        aria-label={`Account: ${username}`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {(username || '?').charAt(0)}
      </button>
      {open && (
        <div className="menu" role="menu">
          <div className="menu__header">
            <div className="muted" style={{ fontSize: 13 }}>Signed in as</div>
            <div className="menu__name">{username}</div>
          </div>
          <button type="button" role="menuitem" className="menu__item" onClick={() => { setOpen(false); onLogout(); }}>
            <LogOut size={18} aria-hidden="true" /> Log out
          </button>
        </div>
      )}
    </div>
  );
}

// onNavigate(path). Without a username (signed out) it offers Log in instead of the account menu.
export function TopBar({ activeTab, onNavigate, savedCount, username, onLogout, onLogin }) {
  return (
    <header className="topbar">
      <div className="topbar__inner">
        <a
          href="/discover"
          className="wordmark"
          onClick={(e) => { e.preventDefault(); onNavigate('/discover'); }}
        >
          <Logo />
        </a>
        <nav className="topnav" aria-label="Main">
          {TABS.map(({ id, path, label, Icon }) => (
            <button
              key={id}
              type="button"
              className="topnav__link"
              aria-current={activeTab === id ? 'page' : undefined}
              onClick={() => onNavigate(path)}
            >
              <Icon size={18} aria-hidden="true" />
              {label}
              {id === 'saved' && savedCount > 0 && <span className="count-badge">{savedCount}</span>}
            </button>
          ))}
        </nav>
        {username ? (
          <AccountMenu username={username} onLogout={onLogout} />
        ) : (
          <button type="button" className="btn btn--primary" onClick={onLogin}>
            <LogIn size={18} aria-hidden="true" /> Log in
          </button>
        )}
      </div>
    </header>
  );
}

export function BottomNav({ activeTab, onNavigate, savedCount }) {
  return (
    <nav className="bottomnav" aria-label="Main">
      {TABS.map(({ id, path, label, Icon }) => (
        <button
          key={id}
          type="button"
          className="bottomnav__link"
          aria-current={activeTab === id ? 'page' : undefined}
          onClick={() => onNavigate(path)}
        >
          <Icon size={22} aria-hidden="true" />
          {label}
          {id === 'saved' && savedCount > 0 && <span className="bottomnav__badge">{savedCount}</span>}
        </button>
      ))}
    </nav>
  );
}

export function Footer() {
  return (
    <footer className="footer">
      <div className="footer__inner">
        <Logo className="footer__logo" />
        <span>Plan your day on a budget · © {new Date().getFullYear()}</span>
      </div>
    </footer>
  );
}
