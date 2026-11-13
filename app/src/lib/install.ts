/** Install prompt rules (SPEC section 7): after the second visit, never on first load; "Not now" = 30 days. */

const VISITS_KEY = 'suki.visits';
const SNOOZE_KEY = 'suki.installSnoozedUntil';
const SESSION_KEY = 'suki.visitCounted';
export const SNOOZE_DAYS = 30;

export interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

function get(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function set(key: string, v: string) {
  try {
    localStorage.setItem(key, v);
  } catch {
    /* ignore */
  }
}

/** Counts this visit once per browser session; returns the total. */
export function countVisit(): number {
  let n = Number(get(VISITS_KEY) ?? '0') || 0;
  try {
    if (!sessionStorage.getItem(SESSION_KEY)) {
      sessionStorage.setItem(SESSION_KEY, '1');
      n += 1;
      set(VISITS_KEY, String(n));
    }
  } catch {
    /* ignore */
  }
  return n;
}

export function snooze(now = Date.now()) {
  set(SNOOZE_KEY, String(now + SNOOZE_DAYS * 86400000));
}

export function isSnoozed(now = Date.now()): boolean {
  return Number(get(SNOOZE_KEY) ?? '0') > now;
}

export function isStandalone(): boolean {
  return (
    (typeof window !== 'undefined' && window.matchMedia?.('(display-mode: standalone)').matches) ||
    (typeof navigator !== 'undefined' && (navigator as Navigator & { standalone?: boolean }).standalone === true)
  );
}

export function isIOS(): boolean {
  if (typeof navigator === 'undefined') return false;
  const ua = navigator.userAgent;
  return /iPad|iPhone|iPod/.test(ua) || (ua.includes('Macintosh') && navigator.maxTouchPoints > 1);
}

export function shouldOfferInstall(visits: number, canPrompt: boolean, now = Date.now()): boolean {
  return visits >= 2 && !isStandalone() && !isSnoozed(now) && (canPrompt || isIOS());
}
