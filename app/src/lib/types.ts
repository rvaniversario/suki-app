export const CATEGORIES = ['fish', 'pork', 'chicken', 'beef'] as const;
export type Category = (typeof CATEGORIES)[number];
export type AnyCategory = Category | 'other';
export type Status = 'buy' | 'ok' | 'skip';

export interface Region {
  id: string;
  name: string;
  status: 'daily' | 'unavailable';
  source?: string;
  hasRange?: boolean;
}

export interface LatestItem {
  id: string;
  name: string;
  category: AnyCategory;
  unit: string;
  price: number | null;
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
