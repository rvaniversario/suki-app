import type { AnyCategory, LatestItem } from './types';

export type Filter = 'all' | AnyCategory;

/**
 * Today's list: tracked goods with a price today (any unit; the score is a percentage). Ranked ascending by score
 * (most below usual first), never by raw price. Items without a baseline go in a
 * separate unranked group.
 */
export function rankItems(items: LatestItem[], tracked: Set<string>, filter: Filter = 'all') {
  const visible = items.filter(
    (i) => tracked.has(i.id) && i.price !== null && (filter === 'all' || i.category === filter),
  );
  const ranked = visible
    .filter((i) => i.pctVsBaseline !== null)
    .sort((a, b) => (a.pctVsBaseline as number) - (b.pctVsBaseline as number) || a.name.localeCompare(b.name));
  const unranked = visible.filter((i) => i.pctVsBaseline === null).sort((a, b) => a.name.localeCompare(b.name));
  return { ranked, unranked };
}
