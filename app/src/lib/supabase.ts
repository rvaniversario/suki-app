import type { SupabaseClient } from '@supabase/supabase-js';
import { accountsEnabled, SUPABASE_ANON_KEY, SUPABASE_URL } from '../config';

let client: Promise<SupabaseClient> | null = null;

/** Loaded on demand so the app never waits on (or breaks without) the backend. */
export function getSupabase(): Promise<SupabaseClient> | null {
  if (!accountsEnabled) return null;
  if (!client) {
    client = import('@supabase/supabase-js').then(({ createClient }) =>
      createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
        auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: 'pkce' },
      }),
    );
  }
  return client;
}
