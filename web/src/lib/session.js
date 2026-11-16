// The login saved on this device. Only a real JWT (three dot-separated parts)
// counts; anything else, such as the old demo login's "mock_token_guest", is
// cleared so the visitor starts signed out instead of with a dead session.
export function loadStoredSession() {
  try {
    const token = localStorage.getItem('otb_token') || '';
    if (token.split('.').length === 3) {
      return { token, username: localStorage.getItem('otb_username') || '' };
    }
    localStorage.removeItem('otb_token');
    localStorage.removeItem('otb_username');
  } catch {
    // storage unavailable (private mode): start signed out
  }
  return { token: '', username: '' };
}
