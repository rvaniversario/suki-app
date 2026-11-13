import { alertsConfigured, VAPID_PUBLIC_KEY } from '../config';
import { isIOS, isStandalone } from './install';
import type { Language } from './settings';
import { getSupabase } from './supabase';

export type PushAvailability = 'available' | 'ios-needs-install' | 'unsupported' | 'not-configured';

export function pushAvailability(): PushAvailability {
  if (typeof window === 'undefined') return 'unsupported';
  if (isIOS() && !isStandalone()) return 'ios-needs-install';
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) return 'unsupported';
  if (!alertsConfigured) return 'not-configured';
  return 'available';
}

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

export interface SubscriptionPrefs {
  region: string;
  trackedIds: string[];
  language: Language;
}

async function save(sub: PushSubscription, prefs: SubscriptionPrefs) {
  const sb = await getSupabase();
  if (!sb) throw new Error('backend not configured');
  const json = sub.toJSON();
  const { error } = await sb.rpc('upsert_push_subscription', {
    p_endpoint: sub.endpoint,
    p_p256dh: json.keys?.p256dh,
    p_auth: json.keys?.auth,
    p_region: prefs.region,
    p_tracked_ids: prefs.trackedIds,
    p_language: prefs.language,
  });
  if (error) throw error;
}

/** Ask permission, subscribe and store the subscription. Returns 'denied' when the user blocks notifications. */
export async function enableAlerts(prefs: SubscriptionPrefs): Promise<'ok' | 'denied'> {
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') return 'denied';
  const reg = await navigator.serviceWorker.ready;
  const sub =
    (await reg.pushManager.getSubscription()) ??
    (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY) }));
  await save(sub, prefs);
  return 'ok';
}

/** Keep the stored row in step with region, tracked goods and language. */
export async function updateAlerts(prefs: SubscriptionPrefs): Promise<void> {
  if (!('serviceWorker' in navigator)) return;
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.getSubscription();
  if (sub) await save(sub, prefs);
}

export async function disableAlerts(): Promise<void> {
  if (!('serviceWorker' in navigator)) return;
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.getSubscription();
  if (!sub) return;
  const sb = await getSupabase();
  const json = sub.toJSON();
  if (sb) await sb.rpc('delete_push_subscription', { p_endpoint: sub.endpoint, p_auth: json.keys?.auth });
  await sub.unsubscribe();
}
