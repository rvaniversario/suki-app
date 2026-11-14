import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useI18n } from '../i18n';
import { BackIcon } from '../components/Icons';
import { marketLine } from '../components/InsightsCard';
import { MarketAiLine, unitSuffix, vsRegionText } from '../components/MarketPrice';
import { LoadState } from '../components/Notices';
import { useInsights } from '../lib/data';
import { dateLong, dateShort, peso } from '../lib/format';
import { marketPrice, pctVsRegion } from '../lib/markets';
import type { LatestItem } from '../lib/types';
import { useApp } from '../state/AppState';
import { useUI } from '../state/UI';
import { groupItems, SearchBox } from './History';

/** Every good with a recent price at "my market", grouped by category, beside the regional price. */
export function Market() {
  const { t, lang } = useI18n();
  const { region, latest, market, marketPrices } = useApp();
  const { openMarketPicker } = useUI();
  const [q, setQ] = useState('');
  const insights = useInsights(region?.id ?? null);

  const priced = useMemo(() => {
    if (!latest.data || !marketPrices.data) return [];
    return latest.data.items.filter((i) => marketPrice(marketPrices.data, i.id));
  }, [latest.data, marketPrices.data]);
  const groups = useMemo(() => groupItems(priced, q), [priced, q]);

  const back = (
    <Link to="/" className="text-link" style={{ alignSelf: 'flex-start' }}>
      <BackIcon />
      {t('nav.today')}
    </Link>
  );

  if (!market) {
    return (
      <div className="page narrow">
        {back}
        <p className="empty">{t('market.noMarket')}</p>
        {region?.markets && (
          <button type="button" className="button-primary" onClick={openMarketPicker}>
            {t('market.pick')}
          </button>
        )}
      </div>
    );
  }

  const row = (i: LatestItem) => {
    const point = marketPrice(marketPrices.data, i.id);
    if (!point) return null;
    const vs = vsRegionText(t, pctVsRegion(point.p, i.price));
    return (
      <li key={i.id}>
        <Link to={`/item/${i.id}`} className="panel-row">
          <span className="label">
            {i.name}
            <small>{[i.detail, vs, point.d !== market.latest ? dateShort(point.d, lang) : null].filter(Boolean).join(' · ')}</small>
          </span>
          <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 }}>
            <span className="price">
              {peso(point.p, lang)}
              <small className="muted"> {unitSuffix(t, i.unit)}</small>
            </span>
            {i.price !== null && <span className="detail">{t('market.regional', { price: peso(i.price, lang) })}</span>}
          </span>
        </Link>
      </li>
    );
  };

  return (
    <div className="page narrow">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {back}
        <h1 className="page-title">{t('market.pageTitle', { market: market.name })}</h1>
        <p className="page-subtitle">{t('market.pageSubtitle', { region: region?.name ?? '' })}</p>
        {market.latest && <p className="as-of">{t('market.asOf', { date: dateLong(market.latest, lang) })}</p>}
        <MarketAiLine line={marketLine(insights.data, market.code, lang)} />
        <button type="button" className="text-link" style={{ alignSelf: 'flex-start' }} onClick={openMarketPicker}>
          {t('common.change')}
        </button>
      </div>
      {!marketPrices.data || !latest.data ? (
        <LoadState
          loading={marketPrices.loading || latest.loading}
          error={marketPrices.error ?? latest.error}
          onRetry={marketPrices.error ? marketPrices.reload : latest.reload}
        />
      ) : priced.length === 0 ? (
        <p className="empty">{t('market.empty')}</p>
      ) : (
        <>
          <SearchBox value={q} onChange={setQ} label={t('history.search')} />
          {groups.length === 0 ? (
            <p className="empty">{t('history.noResults', { q })}</p>
          ) : (
            groups.map(([cat, items]) => (
              <section key={cat} className="section">
                <h2 className="section-title">{t(`categories.${cat}`)}</h2>
                <ul className="panel list">{items.map(row)}</ul>
              </section>
            ))
          )}
        </>
      )}
    </div>
  );
}
