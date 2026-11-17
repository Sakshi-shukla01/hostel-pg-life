// Dev mode only: when the backend has no email (SMTP) set up, it returns the code
// in the API response. We keep it for the next screen in sessionStorage.
const KEY = "hpl_dev_code";

export function saveDevCode(email: string, code?: string) {
  if (!code) return;
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ email: email.toLowerCase(), code }));
  } catch {
    /* storage unavailable */
  }
}

export function readDevCode(email: string): string | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const v = JSON.parse(raw) as { email: string; code: string };
    return v.email === email.toLowerCase() ? v.code : null;
  } catch {
    return null;
  }
}
