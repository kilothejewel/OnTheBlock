import { useLocation, useNavigate } from 'react-router';
import { useSession } from './contexts';

// Sends a signed-out visitor to /login, remembering where they were.
export function useRequireSignIn() {
  const { signedIn } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  // Runs `action` when signed in; otherwise goes to /login and back afterwards.
  return (action) => (...args) => {
    if (!signedIn) {
      navigate('/login', { state: { from: location } });
      return undefined;
    }
    return action(...args);
  };
}
