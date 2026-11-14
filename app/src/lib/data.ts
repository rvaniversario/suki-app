import { useCallback, useEffect, useState } from 'react';
import { DATA_BASE } from '../config';
import type { History, Insights, Latest, MarketIndex, MarketPrices, Region } from './types';

const memo = new Map<string, Promise<unknown>>();

/** For tests. */
export const clearDataCache = () => memo.clear();

/** Fetch a JSON file under /data. The service worker serves it stale-while-revalidate. */
export function fetchData<T>(path: string, fresh = false): Promise<T> {
  if (fresh) memo.delete(path);
  let p = memo.get(path) as Promise<T> | undefined;
  if (!p) {
    p = fetch(`${DATA_BASE}/${path}`).then((r) => {
      if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
      return r.json() as Promise<T>;
    });
    p.catch(() => memo.delete(path));
    memo.set(path, p);
  }
  return p;
}

export interface Async<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  reload: () => void;
}

export function useData<T>(path: string | null): Async<T> {
  const [state, setState] = useState<{ data: T | null; error: Error | null; loading: boolean }>({
    data: null,
    error: null,
    loading: Boolean(path),
  });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!path) {
      setState({ data: null, error: null, loading: false });
      return;
    }
    let live = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    fetchData<T>(path, nonce > 0).then(
      (data) => live && setState({ data, error: null, loading: false }),
      (error: Error) => live && setState({ data: null, error, loading: false }),
    );
    return () => {
      live = false;
    };
  }, [path, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { ...state, reload };
}

export const useRegions = () => useData<Region[]>('regions.json');
export const useLatest = (region: string | null) => useData<Latest>(region ? `${region}/latest.json` : null);
export const useHistory = (region: string | null, id: string | null) =>
  useData<History>(region && id ? `${region}/history/${id}.json` : null);
export const useInsights = (region: string | null) => useData<Insights>(region ? `${region}/insights.json` : null);
export const useMarkets = (region: string | null) => useData<MarketIndex>(region ? `${region}/markets.json` : null);
export const useMarketPrices = (region: string | null, code: string | null) =>
  useData<MarketPrices>(region && code ? `${region}/markets/${code}.json` : null);

export function useOnline(): boolean {
  const [online, setOnline] = useState(typeof navigator === 'undefined' ? true : navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, []);
  return online;
}

export type Breakpoint = 'phone' | 'tablet' | 'desktop';

function currentBreakpoint(): Breakpoint {
  if (typeof window === 'undefined' || !window.matchMedia) return 'phone';
  if (window.matchMedia('(min-width: 1024px)').matches) return 'desktop';
  if (window.matchMedia('(min-width: 640px)').matches) return 'tablet';
  return 'phone';
}

export function useBreakpoint(): Breakpoint {
  const [bp, setBp] = useState<Breakpoint>(currentBreakpoint);
  useEffect(() => {
    if (!window.matchMedia) return;
    const queries = ['(min-width: 1024px)', '(min-width: 640px)'].map((q) => window.matchMedia(q));
    const update = () => setBp(currentBreakpoint());
    queries.forEach((q) => q.addEventListener?.('change', update));
    return () => queries.forEach((q) => q.removeEventListener?.('change', update));
  }, []);
  return bp;
}
