/** Working name; change it here (and in the manifest in vite.config.ts and index.html). */
export const APP_NAME = 'Suki';

export const DATA_BASE = `${import.meta.env.BASE_URL}data`;

export const SUPABASE_URL = (import.meta.env.VITE_SUPABASE_URL as string | undefined) ?? '';
export const SUPABASE_ANON_KEY = (import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined) ?? '';
export const VAPID_PUBLIC_KEY = (import.meta.env.VITE_VAPID_PUBLIC_KEY as string | undefined) ?? '';

export const accountsEnabled = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
export const alertsConfigured = accountsEnabled && Boolean(VAPID_PUBLIC_KEY);

/** A report older than this many days shows a stale-data notice. */
export const STALE_AFTER_DAYS = 3;
