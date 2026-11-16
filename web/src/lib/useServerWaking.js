import { useSyncExternalStore } from 'react';
import { isServerSlow, subscribeServerSlow } from './api';

// True while any API request has been waiting more than 3 seconds.
export function useServerWaking() {
  return useSyncExternalStore(subscribeServerSlow, isServerSlow, () => false);
}
