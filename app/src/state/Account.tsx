import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import type { Session, SupabaseClient } from '@supabase/supabase-js';
import { accountsEnabled } from '../config';
import { mergeOnSignIn, normalize, type Settings } from '../lib/settings';
import { getSupabase } from '../lib/supabase';
import { useApp } from './AppState';

/**
 * Optional account: keeps settings in sync across devices (SPEC section 17).
 * localStorage stays the source the UI reads; Supabase is written through (debounced),
 * pulled on start and on window focus, last write wins by updatedAt.
 */

const PENDING_KEY = 'suki.syncPending';
const PUSH_DEBOUNCE_MS = 1500;

interface Account {
  enabled: boolean;
  email: string | null;
  /** Message to show after sign-in merge ('keptRemote' | 'keptLocal'). */
  notice: string | null;
  clearNotice: () => void;
  signInWithEmail: (email: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  deleteAccount: () => Promise<void>;
}

const Ctx = createContext<Account>({
  enabled: false,
  email: null,
  notice: null,
  clearNotice: () => {},
  signInWithEmail: async () => {},
  signInWithGoogle: async () => {},
  signOut: async () => {},
  deleteAccount: async () => {},
});

const redirectTo = () => `${window.location.origin}${import.meta.env.BASE_URL}settings`;

async function fetchRemote(sb: SupabaseClient, userId: string): Promise<Settings | null> {
  const { data, error } = await sb.from('user_settings').select('settings').eq('user_id', userId).maybeSingle();
  if (error) throw error;
  return data ? normalize(data.settings) : null;
}

async function pushRemote(sb: SupabaseClient, userId: string, s: Settings) {
  const { error } = await sb
    .from('user_settings')
    .upsert({ user_id: userId, settings: s, updated_at: s.updatedAt ?? new Date().toISOString() });
  if (error) throw error;
}

function setPending(v: boolean) {
  try {
    if (v) localStorage.setItem(PENDING_KEY, '1');
    else localStorage.removeItem(PENDING_KEY);
  } catch {
    /* ignore */
  }
}
function isPending() {
  try {
    return localStorage.getItem(PENDING_KEY) === '1';
  } catch {
    return false;
  }
}

export function AccountProvider({ children }: { children: ReactNode }) {
  const { settings, replace } = useApp();
  const [session, setSession] = useState<Session | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const settingsRef = useRef(settings);
  settingsRef.current = settings;
  const lastSynced = useRef<string | null>(null);
  const userId = session?.user.id ?? null;

  // Merge on sign-in; pull on start.
  const reconcile = useCallback(
    async (sb: SupabaseClient, uid: string, isSignIn: boolean) => {
      const local = settingsRef.current;
      const remote = await fetchRemote(sb, uid);
      if (isSignIn) {
        const res = mergeOnSignIn(local, remote);
        if (res.settings !== local) replace(res.settings);
        if (res.upload) await pushRemote(sb, uid, res.settings);
        if (res.kept === 'remote') setNotice('settings.keptRemote');
        if (res.kept === 'local') setNotice('settings.keptLocal');
        lastSynced.current = res.settings.updatedAt;
        return;
      }
      // Regular pull: last write wins.
      const l = Date.parse(local.updatedAt ?? '') || 0;
      const r = Date.parse(remote?.updatedAt ?? '') || 0;
      if (remote && r > l) {
        replace({ ...remote, region: remote.region ?? local.region });
        lastSynced.current = remote.updatedAt;
      } else if (l > r || isPending()) {
        await pushRemote(sb, uid, local);
        setPending(false);
        lastSynced.current = local.updatedAt;
      }
    },
    [replace],
  );

  useEffect(() => {
    const p = getSupabase();
    if (!p) return;
    let unsub: (() => void) | undefined;
    p.then((sb) => {
      sb.auth.getSession().then(({ data }) => {
        setSession(data.session);
        if (data.session) reconcile(sb, data.session.user.id, false).catch(() => setPending(true));
      });
      const { data } = sb.auth.onAuthStateChange((event, s) => {
        setSession(s);
        if (event === 'SIGNED_IN' && s) reconcile(sb, s.user.id, true).catch(() => setPending(true));
      });
      unsub = () => data.subscription.unsubscribe();
    });
    return () => unsub?.();
  }, [reconcile]);

  // Pull on focus, flush the offline queue when back online.
  useEffect(() => {
    const p = getSupabase();
    if (!p || !userId) return;
    const pull = () => p.then((sb) => reconcile(sb, userId, false)).catch(() => {});
    window.addEventListener('focus', pull);
    window.addEventListener('online', pull);
    return () => {
      window.removeEventListener('focus', pull);
      window.removeEventListener('online', pull);
    };
  }, [userId, reconcile]);

  // Write through on change (debounced).
  useEffect(() => {
    const p = getSupabase();
    if (!p || !userId || settings.updatedAt === lastSynced.current) return;
    const timer = setTimeout(() => {
      p.then((sb) => pushRemote(sb, userId, settingsRef.current))
        .then(() => {
          lastSynced.current = settingsRef.current.updatedAt;
          setPending(false);
        })
        .catch(() => setPending(true));
    }, PUSH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [settings, userId]);

  const value: Account = {
    enabled: accountsEnabled,
    email: session?.user.email ?? null,
    notice,
    clearNotice: () => setNotice(null),
    signInWithEmail: async (email) => {
      const sb = await getSupabase();
      if (!sb) return;
      const { error } = await sb.auth.signInWithOtp({ email, options: { emailRedirectTo: redirectTo() } });
      if (error) throw error;
    },
    signInWithGoogle: async () => {
      const sb = await getSupabase();
      if (!sb) return;
      const { error } = await sb.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: redirectTo() } });
      if (error) throw error;
    },
    signOut: async () => {
      // Local settings stay on the device.
      const sb = await getSupabase();
      await sb?.auth.signOut();
    },
    deleteAccount: async () => {
      const sb = await getSupabase();
      if (!sb) return;
      const { error } = await sb.rpc('delete_my_account');
      if (error) throw error;
      await sb.auth.signOut();
    },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useAccount = () => useContext(Ctx);
