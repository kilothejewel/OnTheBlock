import { useEffect, useState } from 'react';
import { ArrowRight, LoaderCircle, CircleAlert } from 'lucide-react';
import Logo from './Logo';
import { AUTH_PHOTO } from '../lib/places';

export default function AuthScreen({ authMode, onModeChange, authForm, setAuthForm, authLoading, authError, onSubmit }) {
  // If the photo can't load (offline, blocked), the panel stays solid brand red.
  const [photoFailed, setPhotoFailed] = useState(false);
  // A hosted API on a free plan sleeps when idle; say so if a request is slow.
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!authLoading) return undefined;
    const timer = setTimeout(() => setSlow(true), 5000);
    return () => {
      clearTimeout(timer);
      setSlow(false);
    };
  }, [authLoading]);
  const isLogin = authMode === 'login';
  const update = (key) => (e) => setAuthForm((f) => ({ ...f, [key]: e.target.value }));

  return (
    <div className="auth">
      <aside className="auth__visual" aria-hidden="true">
        {!photoFailed && <img className="auth__visual-photo" src={AUTH_PHOTO} alt="" onError={() => setPhotoFailed(true)} />}
        <Logo className="logo--inverse auth__visual-logo" />
        <div className="auth__visual-copy">
          <h2>Your city, one block at a time.</h2>
          <p>Find the spots people are talking about and turn them into a day plan that fits your budget.</p>
        </div>
      </aside>

      <main className="auth__panel">
        <div className="auth__card">
          <div className="auth__brand">
            <Logo className="auth__logo" />
            <h1 className="section-title" style={{ fontSize: 24, lineHeight: '32px' }}>
              {isLogin ? 'Welcome back' : 'Create your account'}
            </h1>
            <p className="muted">
              {isLogin
                ? 'Log in to see your saved trips and places.'
                : 'Save places you love and plan days out that fit your budget.'}
            </p>
          </div>

          <div className="segmented" role="radiogroup" aria-label="Account">
            {[['login', 'Log in'], ['register', 'Sign up']].map(([mode, label]) => (
              <button
                key={mode}
                type="button"
                role="radio"
                aria-checked={authMode === mode}
                className="segmented__option"
                onClick={() => onModeChange(mode)}
              >
                {label}
              </button>
            ))}
          </div>

          <form className="auth__form" onSubmit={onSubmit}>
            {isLogin ? (
              <div className="field">
                <label className="field__label" htmlFor="auth-identifier">Email or username</label>
                <input
                  id="auth-identifier"
                  className="input"
                  type="text"
                  autoComplete="username"
                  placeholder="you@example.com"
                  value={authForm.identifier}
                  onChange={update('identifier')}
                  required
                />
              </div>
            ) : (
              <>
                <div className="field">
                  <label className="field__label" htmlFor="auth-email">Email</label>
                  <input
                    id="auth-email"
                    className="input"
                    type="email"
                    autoComplete="email"
                    placeholder="you@example.com"
                    value={authForm.email}
                    onChange={update('email')}
                    required
                  />
                </div>
                <div className="field">
                  <label className="field__label" htmlFor="auth-username">Username</label>
                  <input
                    id="auth-username"
                    className="input"
                    type="text"
                    autoComplete="username"
                    value={authForm.username}
                    onChange={update('username')}
                    required
                    minLength={3}
                    aria-describedby="auth-username-hint"
                  />
                  <span id="auth-username-hint" className="field__hint">At least 3 characters.</span>
                </div>
              </>
            )}

            <div className="field">
              <label className="field__label" htmlFor="auth-password">Password</label>
              <input
                id="auth-password"
                className="input"
                type="password"
                autoComplete={isLogin ? 'current-password' : 'new-password'}
                value={authForm.password}
                onChange={update('password')}
                required
                minLength={isLogin ? undefined : 8}
                aria-describedby={isLogin ? undefined : 'auth-password-hint'}
              />
              {!isLogin && <span id="auth-password-hint" className="field__hint">At least 8 characters.</span>}
            </div>

            {authError && (
              <div className="form-error" role="alert">
                <CircleAlert size={18} aria-hidden="true" style={{ flexShrink: 0, marginTop: 1 }} />
                <span>{authError}</span>
              </div>
            )}

            <button type="submit" className="btn btn--primary btn--lg btn--block" disabled={authLoading}>
              {authLoading ? (
                <><LoaderCircle size={18} className="spinner" aria-hidden="true" /> {isLogin ? 'Logging in…' : 'Creating account…'}</>
              ) : (
                <>{isLogin ? 'Log in' : 'Create account'} <ArrowRight size={18} aria-hidden="true" /></>
              )}
            </button>
            {authLoading && slow && (
              <p className="field__hint" role="status" style={{ textAlign: 'center' }}>
                Waking up the server. On the free hosting plan this can take up to a minute.
              </p>
            )}
          </form>
        </div>
      </main>
    </div>
  );
}
