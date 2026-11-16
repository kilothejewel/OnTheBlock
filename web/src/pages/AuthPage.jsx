import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router';
import AuthScreen from '../components/AuthScreen';
import { apiFetch } from '../lib/api';
import { useSession, useToast } from '../state/contexts';

const EMPTY_AUTH_FORM = { identifier: '', email: '', username: '', password: '' };

// Where to go after signing in: the screen that sent the visitor here, else Discover.
function returnPath(location) {
  const from = location.state?.from;
  if (!from?.pathname || from.pathname === '/login' || from.pathname === '/signup') return '/discover';
  return `${from.pathname}${from.search || ''}`;
}

// /login and /signup. mode: 'login' | 'register'
export default function AuthPage({ mode }) {
  const { signedIn, signIn } = useSession();
  const { notify } = useToast();
  const location = useLocation();
  const navigate = useNavigate();
  const [authForm, setAuthForm] = useState(EMPTY_AUTH_FORM);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState('');

  if (signedIn) return <Navigate to={returnPath(location)} replace />;

  const isRegister = mode === 'register';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setAuthError('');

    const endpoint = isRegister ? '/auth/register' : '/auth/login';
    const payload = isRegister
      ? { email: authForm.email.trim(), username: authForm.username.trim(), password: authForm.password }
      : { identifier: authForm.identifier.trim(), password: authForm.password };

    if (isRegister && (!payload.email || !payload.username || !payload.password)) {
      setAuthError('Email, username, and password are all required.');
      return;
    }
    if (!isRegister && (!payload.identifier || !payload.password)) {
      setAuthError('Enter your email/username and password.');
      return;
    }

    setAuthLoading(true);
    try {
      const { access_token: jwt } = await apiFetch(endpoint, { method: 'POST', body: payload });

      // Resolve the canonical username from the API.
      let name = isRegister ? payload.username : payload.identifier;
      try {
        const me = await apiFetch('/auth/me', { token: jwt });
        name = me.username || name;
      } catch {
        // non-fatal: fall back to the value entered
      }

      setAuthLoading(false);
      signIn(jwt, name);
      notify(isRegister ? `Welcome to On the Block, ${name}!` : `Welcome back, ${name}!`, 'success');
      navigate(returnPath(location), { replace: true });
    } catch (err) {
      setAuthError(err.message || 'Please check your details and try again.');
      setAuthLoading(false);
    }
  };

  return (
    <AuthScreen
      authMode={mode}
      onModeChange={(next) => {
        setAuthError('');
        navigate(next === 'register' ? '/signup' : '/login', { replace: true, state: location.state });
      }}
      authForm={authForm}
      setAuthForm={setAuthForm}
      authLoading={authLoading}
      authError={authError}
      onSubmit={handleSubmit}
    />
  );
}
