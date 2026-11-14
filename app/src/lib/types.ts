/** Categories in the weekly plan (usual kilos per week). */
export const CATEGORIES = ['fish', 'pork', 'chicken', 'beef'] as const;
export type Category = (typeof CATEGORIES)[number];
/** Every category, in display order. */
export const ALL_CATEGORIES = [...CATEGORIES, 'eggs', 'rice', 'vegetables', 'fruits', 'spices', 'other'] as const;
export type AnyCategory = (typeof ALL_CATEGORIES)[number];
export type Status = 'buy' | 'ok' | 'skip';

export interface Region {
  id: string;
  name: string;
  status: 'daily' | 'unavailable';
  source?: string;
  hasRange?: boolean;
  /** Per-market prices are published for this region (data/{region}/markets.json). */
  markets?: boolean;
}

export interface InsightDish {
  name: string;
  why: string;
  ingredients: { id: string; name: string; qty: number; unit: string; cost: number }[];
  /** Pesos, computed by the scraper from current prices (never by the AI). */
  cost: number;
}

export interface InsightNote {
  brief: string;
  dishes: InsightDish[];
  notes: string[];
}

/** AI-written weekly note per region (data/{region}/insights.json). */
export interface Insights {
  region: string;
  asOf: string;
  generatedAt: string;
  model: string;
  en: InsightNote;
  fil: InsightNote;
  /** One AI line per market code. */
  markets?: Record<string, { en: string; fil: string }>;
  /** Why big movers moved, from a web search; every source was returned by that search. */
  why?: { goods: string[]; en: string; fil: string; sources: { title: string; url: string }[] } | null;
}

export interface MarketInfo {
  code: string;
  name: string;
  lat: number | null;
  lng: number | null;
  /** Newest price date at this market. */
  latest: string | null;
  items: number;
}

export interface MarketIndex {
  region: string;
  source: string;
  markets: MarketInfo[];
}

export interface MarketPoint {
  d: string;
  p: number;
  lo?: number;
  hi?: number;
}

export interface MarketPrices {
  code: string;
  name: string;
  region: string;
  latest: string | null;
  items: Record<string, MarketPoint>;
}

export interface LatestItem {
  id: string;
  name: string;
  category: AnyCategory;
  unit: string;
  price: number | null;
  /** Date of `price`: the item's newest available price, which can be older than `asOf`. */
  date?: string | null;
  low: number | null;
  high: number | null;
  baseline: number | null;
  pctVsBaseline: number | null;
  status: Status | null;
  daysOfHistory: number;
  featured: boolean;
  lowest90?: boolean;
  detail?: string;
}

export interface Latest {
  region: string;
  asOf: string;
  generatedAt: string;
  items: LatestItem[];
}

export interface HistoryPoint {
  d: string;
  p: number | null;
  lo?: number;
  hi?: number;
  m?: number;
}

export interface History {
  id: string;
  points: HistoryPoint[];
}
