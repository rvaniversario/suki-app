import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { APP_NAME } from '../config';
import { useI18n } from '../i18n';
import { ChevronDown, SettingsIcon } from '../components/Icons';
import { MarketBar, MarketPriceLine, PriceDate, unitSuffix, useMarketPoint } from '../components/MarketPrice';
import { InsightsCard } from '../components/InsightsCard';
import { LoadState, ReportNotices } from '../components/Notices';
import { PlanSummary } from '../components/PlanSummary';
import { PriceChart } from '../components/PriceChart';
import { StatusChip } from '../components/StatusChip';
import { useBreakpoint, useHistory } from '../lib/data';
import { kg, peso } from '../lib/format';
import { rankItems, type Filter } from '../lib/ranking';
import { ALL_CATEGORIES, type LatestItem } from '../lib/types';
import { useApp } from '../state/AppState';
import { useUI } from '../state/UI';


export function RegionPill() {
  const { t } = useI18n();
  const { region } = useApp();
  const { openRegionPicker } = useUI();
  const name = region?.name ?? t('region.pick');
  return (
    <button type="button" className="pill-button" onClick={openRegionPicker} aria-label={t('today.regionAria', { region: name })}>
      {name}
      <ChevronDown />
    </button>
  );
}

/** "All" plus every category that has a tracked good with a price today. */
function filtersFor(items: LatestItem[], tracked: Set<string>): Filter[] {
  const present = new Set(items.filter((i) => tracked.has(i.id) && i.price !== null).map((i) => i.category));
  return ['all', ...ALL_CATEGORIES.filter((c) => present.has(c))];
}

function FilterChips({ filters, value, onChange }: { filters: Filter[]; value: Filter; onChange: (f: Filter) => void }) {
  const { t } = useI18n();
  if (filters.length <= 2) return null;
  return (
    <div className="chips" role="group" aria-label={t('today.filterLabel')}>
      {filters.map((f) => (
        <button key={f} type="button" className="chip" aria-pressed={value === f} onClick={() => onChange(f)}>
          {t(`categories.${f}`)}
        </button>
      ))}
    </div>
  );
}

function PriceText({ item }: { item: LatestItem }) {
  const { t, lang } = useI18n();
  return (
    <span className="price">
      {peso(item.price, lang)}
      <small> {unitSuffix(t, item.unit)}</small>
    </span>
  );
}

function RankList({ items, offset = 0 }: { items: LatestItem[]; offset?: number }) {
  return (
    <ol className="ranked">
      {items.map((item, i) => (
        <li key={item.id}>
          <Link to={`/item/${item.id}`} className="rank-row">
            <span className="rank-num">{item.pctVsBaseline === null ? '' : offset + i + 1}</span>
            <span className="rank-name">
              <strong>{item.name}</strong>
              {item.detail && <span>{item.detail}</span>}
              <PriceDate item={item} />
              <MarketPriceLine item={item} />
            </span>
            <span className="rank-price">
              <PriceText item={item} />
              <StatusChip item={item} />
            </span>
          </Link>
        </li>
      ))}
    </ol>
  );
}

function CardGrid({ items }: { items: LatestItem[] }) {
  const { t, lang } = useI18n();
  return (
    <ol className="card-grid">
      {items.map((item, i) => (
        <li key={item.id}>
          <Link to={`/item/${item.id}`} className="item-card">
            <span className="row">
              <span className="num muted" style={{ fontWeight: 600 }}>
                {item.pctVsBaseline === null ? '' : t('today.rank', { rank: i + 1 })}
              </span>
              <StatusChip item={item} large />
            </span>
            <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span className="name">{item.name}</span>
              {item.detail && <span className="detail">{item.detail}</span>}
              <PriceDate item={item} />
              <MarketPriceLine item={item} />
            </span>
            <span className="row" style={{ alignItems: 'baseline' }}>
              <span className="big-price">
                {peso(item.price, lang)}
                <small className="muted" style={{ fontFamily: 'var(--font-text)', fontSize: 13, fontWeight: 400 }}>
                  {' '}
                  {unitSuffix(t, item.unit)}
                </small>
              </span>
              {item.baseline !== null && <span className="detail">{t('today.usual', { price: peso(item.baseline, lang) })}</span>}
            </span>
          </Link>
        </li>
      ))}
    </ol>
  );
}

function RankTable({ items, selected, onSelect }: { items: LatestItem[]; selected: string | null; onSelect: (id: string) => void }) {
  const { t, lang } = useI18n();
  const { plan, market } = useApp();
  const weekQty = (id: string) => {
    const row = plan?.rows.find((r) => r.item.id === id);
    return row ? kg(row.kg) : '—';
  };
  return (
    <div className="table-wrap">
      <table className="rank-table">
        <thead>
          <tr>
            <th scope="col">{t('today.colRank')}</th>
            <th scope="col">{t('today.colItem')}</th>
            <th scope="col" className="r">
              {t('today.colPrice')}
            </th>
            <th scope="col" className="r">
              {t('today.colUsual')}
            </th>
            {market && (
              <th scope="col" className="r">
                {t('market.colMarket')}
              </th>
            )}
            <th scope="col">{t('today.colAgainst')}</th>
            <th scope="col" className="r">
              {t('today.colWeek')}
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => (
            <tr key={item.id} aria-selected={selected === item.id} onClick={() => onSelect(item.id)}>
              <td className="num muted" style={{ fontWeight: 600 }}>
                {item.pctVsBaseline === null ? '' : i + 1}
              </td>
              <td>
                <button type="button" className="item-button" onClick={() => onSelect(item.id)} aria-pressed={selected === item.id}>
                  <strong>{item.name}</strong>
                  {item.detail && <span className="detail">{item.detail}</span>}
                  <PriceDate item={item} />
                </button>
              </td>
              <td className="r price">
                {peso(item.price, lang)}
                {item.unit !== 'kg' && <small className="muted"> {unitSuffix(t, item.unit)}</small>}
              </td>
              <td className="r muted" style={{ fontSize: 14 }}>
                {peso(item.baseline, lang)}
              </td>
              {market && <MarketCell id={item.id} />}
              <td>
                <StatusChip item={item} />
              </td>
              <td className="r num" style={{ fontWeight: 600 }}>
                {weekQty(item.id)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MarketCell({ id }: { id: string }) {
  const { lang } = useI18n();
  const point = useMarketPoint(id);
  return (
    <td className="r" style={{ fontSize: 14 }}>
      {peso(point?.p ?? null, lang)}
    </td>
  );
}

function SelectedChart({ item }: { item: LatestItem }) {
  const { t } = useI18n();
  const { region, latest } = useApp();
  const history = useHistory(region?.id ?? null, item.id);
  return (
    <div className="chart-card" style={{ padding: '18px 16px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8, padding: '0 6px' }}>
        <h2 style={{ fontSize: 16, lineHeight: '22px', fontWeight: 600 }}>{item.name}</h2>
        <span className="detail">{t('today.chartRange')}</span>
      </div>
      {history.data && latest.data && (
        <PriceChart name={item.name} points={history.data.points} asOf={latest.data.asOf} rangeDays={90} baseline={item.baseline} />
      )}
      <Link to={`/item/${item.id}`} className="text-link" style={{ padding: '0 6px' }}>
        {t('today.details')}
      </Link>
    </div>
  );
}

export function Today() {
  const { t } = useI18n();
  const bp = useBreakpoint();
  const { latest, tracked, region, plan, regions } = useApp();
  const [filterChoice, setFilter] = useState<Filter>('all');
  const filters = useMemo(() => filtersFor(latest.data?.items ?? [], tracked), [latest.data, tracked]);
  const filter = filters.includes(filterChoice) ? filterChoice : 'all';
  const [selected, setSelected] = useState<string | null>(null);

  const { ranked, unranked } = useMemo(
    () => (latest.data ? rankItems(latest.data.items, tracked, filter) : { ranked: [], unranked: [] }),
    [latest.data, tracked, filter],
  );
  const all = [...ranked, ...unranked];
  const selectedItem = all.find((i) => i.id === selected) ?? all[0] ?? null;
  const empty = !ranked.length && !unranked.length;
  const emptyText = filter === 'all' ? t('today.empty') : t('today.emptyFilter', { category: t(`categories.${filter}`).toLowerCase() });

  const heading = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <h1 className="page-title">{t('today.title')}</h1>
      <p className="page-subtitle">{t('today.subtitle')}</p>
    </div>
  );

  const body = latest.data ? (
    <>
      <ReportNotices asOf={latest.data.asOf} source={region?.source} />
      <MarketBar />
      <InsightsCard />
      <FilterChips filters={filters} value={filter} onChange={setFilter} />
      {bp === 'tablet' && plan && plan.rows.length > 0 && <PlanSummary plan={plan} variant="strip" />}
      {empty && <p className="empty">{emptyText}</p>}
      {bp === 'phone' && (
        <>
          {ranked.length > 0 && <RankList items={ranked} />}
          {unranked.length > 0 && (
            <>
              <h2 className="group-title">{t('today.unrankedTitle')}</h2>
              <p className="help">{t('today.unrankedHint')}</p>
              <RankList items={unranked} />
            </>
          )}
        </>
      )}
      {bp === 'tablet' && (
        <>
          {ranked.length > 0 && <CardGrid items={ranked} />}
          {unranked.length > 0 && (
            <>
              <h2 className="group-title">{t('today.unrankedTitle')}</h2>
              <p className="help">{t('today.unrankedHint')}</p>
              <CardGrid items={unranked} />
            </>
          )}
        </>
      )}
      {bp === 'desktop' && !empty && (
        <div className="desktop-cols">
          <RankTable items={all} selected={selectedItem?.id ?? null} onSelect={setSelected} />
          <div className="side">
            {plan && plan.rows.length > 0 && <PlanSummary plan={plan} variant="side" />}
            {selectedItem && <SelectedChart item={selectedItem} />}
          </div>
        </div>
      )}
    </>
  ) : region || regions.loading ? (
    <LoadState loading={latest.loading || regions.loading} error={latest.error ?? regions.error} onRetry={latest.data ? latest.reload : regions.reload} />
  ) : (
    <LoadState loading={false} error={regions.error} onRetry={regions.reload} />
  );

  if (bp === 'phone') {
    return (
      <>
        <header className="top-header">
          <div className="top-row">
            <span className="app-name">{APP_NAME}</span>
            <div className="top-actions">
              <RegionPill />
              <Link to="/settings" className="icon-button" aria-label={t('nav.settings')}>
                <SettingsIcon />
              </Link>
            </div>
          </div>
          <div style={{ marginTop: 4 }}>{heading}</div>
        </header>
        <div className="page" style={{ paddingTop: 0 }}>
          {body}
        </div>
      </>
    );
  }
  return (
    <div className="page">
      <div className="title-row">
        {heading}
        <RegionPill />
      </div>
      {body}
    </div>
  );
}
