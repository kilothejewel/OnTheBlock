// The app's shared state, split by concern. Each context has a provider in
// this folder (providers.jsx) and a hook here to read it.
import { createContext, useContext } from 'react';

export const ToastContext = createContext(null);
export const SessionContext = createContext(null);
export const LibraryContext = createContext(null);
export const PlanningContext = createContext(null);

function useRequired(context, name) {
  const value = useContext(context);
  if (value === null) throw new Error(`${name} must be used inside its provider (see state/providers.jsx).`);
  return value;
}

// notify(message, type) shows a toast; reportError(err, fallback) shows a failed request.
export const useToast = () => useRequired(ToastContext, 'useToast');
// token, username, signedIn, signIn(jwt, name), signOut(), api(path, options)
export const useSession = () => useRequired(SessionContext, 'useSession');
// The signed-in user's Saved places and Trips.
export const useLibrary = () => useRequired(LibraryContext, 'useLibrary');
// The city, the Discover search and the Plan being made.
export const usePlanning = () => useRequired(PlanningContext, 'usePlanning');
