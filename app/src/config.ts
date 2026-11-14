/** Working name; change it here (and in the manifest in vite.config.ts and index.html). */
export const APP_NAME = 'Suki';

/**
 * Where the price JSON lives. Empty: served by this site under /data (Docker). Set VITE_DATA_URL when
 * the app is hosted apart from its data, e.g. on Vercel with the data in Supabase Storage:
 * https://<project>.supabase.co/storage/v1/object/public/prices
 */
const DATA_URL = ((import.meta.env.VITE_DATA_URL as string | undefined) ?? '').trim().replace(/\/+$/, '');
export const DATA_BASE = DATA_URL || `${import.meta.env.BASE_URL}data`;

export const SUPABASE_URL = (import.meta.env.VITE_SUPABASE_URL as string | undefined) ?? '';
export const SUPABASE_ANON_KEY = (import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined) ?? '';
export const VAPID_PUBLIC_KEY = (import.meta.env.VITE_VAPID_PUBLIC_KEY as string | undefined) ?? '';

export const accountsEnabled = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
export const alertsConfigured = accountsEnabled && Boolean(VAPID_PUBLIC_KEY);

/** A report older than this many days shows a stale-data notice. */
export const STALE_AFTER_DAYS = 3;
