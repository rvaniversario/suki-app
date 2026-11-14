import type { MarketIndex, MarketInfo, MarketPoint, MarketPrices } from './types';

/** Markets by name. Every market is shown, whatever the date of its newest price. */
export function sortMarkets(index: MarketIndex): MarketInfo[] {
  return [...index.markets].sort((a, b) => a.name.localeCompare(b.name));
}

/** The market's newest price for an item (with its date), however old. */
export function marketPrice(prices: MarketPrices | null | undefined, itemId: string): MarketPoint | null {
  return prices?.items[itemId] ?? null;
}

/** Percent difference of the market price from the regional price, rounded; null when either is missing. */
export function pctVsRegion(market: number | null | undefined, region: number | null | undefined): number | null {
  if (market == null || region == null || region === 0) return null;
  return Math.round(((market - region) / region) * 100);
}
