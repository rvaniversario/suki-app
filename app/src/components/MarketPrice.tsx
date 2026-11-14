import { Link } from 'react-router-dom';
import type { TFunction } from '../i18n';
import { useI18n } from '../i18n';
import { useInsights } from '../lib/data';
import { marketLine } from './InsightsCard';
import { dateLong, dateShort, peso } from '../lib/format';
import { marketPrice, pctVsRegion } from '../lib/markets';
import type { LatestItem, MarketPoint } from '../lib/types';
import { useApp } from '../state/AppState';
import { useUI } from '../state/UI';

/** "/kg", "/pc", "/bottle" (or "/unit" for anything else). */
export function unitSuffix(t: TFunction, unit: string): string {
  const key = `units.${unit}`;
  const s = t(key);
  return s === key ? `/${unit}` : s;
}

/** "per kilo", "per piece", ... */
export function unitLong(t: TFunction, unit: string): string {
  const key = `unitsLong.${unit}`;
  const s = t(key);
  return s === key ? `/ ${unit}` : s;
}

/** "Price from Nov 3" when an item's newest price is older than the region's newest report. */
export function PriceDate({ item }: { item: LatestItem }) {
  const { t, lang } = useI18n();
  const { latest } = useApp();
  if (!item.date || item.date === latest.data?.asOf) return null;
  return <span className="market-line">{t('common.priceFrom', { date: dateShort(item.date, lang) })}</span>;
}

/** The chosen market's newest price for an item (however old), or null. */
export function useMarketPoint(itemId: string): MarketPoint | null {
  const { market, marketPrices } = useApp();
  if (!market || !marketPrices.data) return null;
  return marketPrice(marketPrices.data, itemId);
}

/** Small line under an item: "Bankerohan: ₱160.00" (plus the date when it is not the market's newest). */
export function MarketPriceLine({ item }: { item: LatestItem }) {
  const { t, lang } = useI18n();
  const { market } = useApp();
  const point = useMarketPoint(item.id);
  if (!market || !point) return null;
  const text = t('market.price', { market: market.name, price: peso(point.p, lang) });
  return <span className="market-line">{point.d === market.latest ? text : `${text} · ${dateShort(point.d, lang)}`}</span>;
}

export function vsRegionText(t: TFunction, pct: number | null): string | null {
  if (pct === null) return null;
  if (pct === 0) return t('market.vsSame');
  return t(pct > 0 ? 'market.vsAbove' : 'market.vsBelow', { pct: Math.abs(pct) });
}

/** Today: which market is chosen and the date of its newest prices, or an invitation to choose one. */
export function MarketBar() {
  const { t, lang } = useI18n();
  const { region, market, markets } = useApp();
  const { openMarketPicker } = useUI();
  const insights = useInsights(region?.id ?? null);
  if (!region?.markets || !markets.data || markets.data.markets.length === 0) return null;
  if (!market) {
    return (
      <button type="button" className="text-link" style={{ alignSelf: 'flex-start' }} onClick={openMarketPicker}>
        {t('market.pick')}
      </button>
    );
  }
  return (
    <div className="market-bar">
      <span className="label">
        <strong>{t('market.mine', { market: market.name })}</strong>
        {market.latest && <small>{t('market.asOf', { date: dateLong(market.latest, lang) })}</small>}
        <MarketAiLine line={marketLine(insights.data, market.code, lang)} />
      </span>
      <span className="actions">
        <Link to="/market" className="text-link">
          {t('market.seeAll')}
        </Link>
        <button type="button" className="text-link" onClick={openMarketPicker}>
          {t('common.change')}
        </button>
      </span>
    </div>
  );
}

/** The AI's one-line summary of a market, labelled as AI-written. */
export function MarketAiLine({ line }: { line: string | null }) {
  const { t } = useI18n();
  if (!line) return null;
  return (
    <small className="market-ai">
      {line} <span className="muted">({t('insights.aiTag')})</span>
    </small>
  );
}

/** Item screen: the market's price beside the regional one. */
export function MarketCompare({ item }: { item: LatestItem }) {
  const { t, lang } = useI18n();
  const { market } = useApp();
  const point = useMarketPoint(item.id);
  if (!market) return null;
  if (!point) return <span className="detail">{t('market.notReported', { market: market.name })}</span>;
  const vs = vsRegionText(t, pctVsRegion(point.p, item.price));
  return (
    <div className="market-compare">
      <span className="label">{market.name}</span>
      <span className="price">
        {peso(point.p, lang)} <small className="muted">{unitSuffix(t, item.unit)}</small>
      </span>
      <span className="detail">{[vs, t('market.dated', { date: dateLong(point.d, lang) })].filter(Boolean).join(' · ')}</span>
    </div>
  );
}
