import { useI18n, type TFunction } from '../i18n';
import type { LatestItem } from '../lib/types';
import { Dash, DownArrow, UpArrow } from './Icons';

export function chipText(t: TFunction, pct: number | null): string {
  if (pct === null) return t('chip.noHistory');
  // Truncate toward zero so the number never disagrees with the status colour
  // (e.g. -3.9 is "ok" and reads "3% below usual", not "4%").
  const n = Math.abs(Math.trunc(pct));
  if (n === 0) return t('chip.same');
  return t(pct < 0 ? 'chip.below' : 'chip.above', { pct: n });
}

/** Status is never colour alone: icon + text + colour. */
export function StatusChip({ item, large }: { item: Pick<LatestItem, 'status' | 'pctVsBaseline'>; large?: boolean }) {
  const { t } = useI18n();
  const status = item.status ?? 'none';
  const pct = item.pctVsBaseline;
  const icon = status === 'buy' ? <DownArrow /> : status === 'skip' ? <UpArrow /> : <Dash />;
  return (
    <span className={`status ${status}${large ? ' lg' : ''}`}>
      {icon}
      {chipText(t, pct)}
    </span>
  );
}
