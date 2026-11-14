import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useI18n } from '../i18n';
import { BackIcon } from '../components/Icons';
import { MarketCompare, PriceDate, unitLong } from '../components/MarketPrice';
import { LoadState } from '../components/Notices';
import { PriceChart } from '../components/PriceChart';
import { StatusChip } from '../components/StatusChip';
import { useHistory } from '../lib/data';
import { kg, peso, pesoWhole } from '../lib/format';
import { suggestedKg } from '../lib/plan';
import { withPick } from '../lib/planStore';
import { CATEGORIES, type Category } from '../lib/types';
import { useApp } from '../state/AppState';

const RANGES = [30, 90, 365] as const;
type Range = (typeof RANGES)[number];

const dayNum = (iso: string) => Math.round(Date.parse(`${iso}T00:00:00Z`) / 86400000);

export function Item() {
  const { id = '' } = useParams();
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const { region, latest, settings, plan, overrides, setOverrides } = useApp();
  const [range, setRange] = useState<Range>(90);
  const item = latest.data?.items.find((i) => i.id === id) ?? null;
  const history = useHistory(region?.id ?? null, item ? id : null);

  const stats = useMemo(() => {
    if (!history.data || !latest.data) return null;
    const end = dayNum(latest.data.asOf);
    const vals = history.data.points
      .filter((p) => p.p !== null && dayNum(p.d) > end - range && dayNum(p.d) <= end)
      .map((p) => p.p as number);
    if (!vals.length) return null;
    return { low: Math.min(...vals), high: Math.max(...vals) };
  }, [history.data, latest.data, range]);

  const back = (
    <button type="button" className="text-link" style={{ alignSelf: 'flex-start' }} onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/'))}>
      <BackIcon />
      {t('common.back')}
    </button>
  );

  if (!latest.data) {
    return (
      <div className="page narrow">
        {back}
        <LoadState loading={latest.loading} error={latest.error} onRetry={latest.reload} />
      </div>
    );
  }
  if (!item) {
    return (
      <div className="page narrow">
        {back}
        <p className="empty">{t('item.notFound', { region: region?.name ?? '' })}</p>
      </div>
    );
  }

  const isPlanCategory = (CATEGORIES as readonly string[]).includes(item.category);
  const category = item.category as Category;
  const suggestion = isPlanCategory && item.price !== null && item.unit === 'kg' ? suggestedKg(settings.usualKg[category], item.pctVsBaseline) : null;
  const inPlan = plan?.rows.find((r) => r.item.id === item.id);

  return (
    <div className="page narrow">
      {back}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <h1 className="page-title">{item.name}</h1>
        <p className="page-subtitle" style={{ fontSize: 14, lineHeight: '20px' }}>
          {[item.detail, region?.name].filter(Boolean).join(' · ')}
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {item.price !== null ? (
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, flexWrap: 'wrap' }}>
            <span className="big-figure">{peso(item.price, lang)}</span>
            <span className="muted" style={{ fontSize: 15 }}>
              {unitLong(t, item.unit)}
            </span>
          </div>
        ) : (
          <p className="notice neutral">{t('item.noPrice')}</p>
        )}
        <PriceDate item={item} />
        {item.price !== null && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <StatusChip item={item} large />
            {item.lowest90 && <span className="detail">{t('item.lowest')}</span>}
          </div>
        )}
        {region?.hasRange && item.low !== null && item.high !== null && (
          <span className="detail">{t('item.range', { low: pesoWhole(item.low, lang), high: pesoWhole(item.high, lang) })}</span>
        )}
        <MarketCompare item={item} />
      </div>

      <div className="segmented" role="group" aria-label={t('item.rangeGroup')}>
        {RANGES.map((r) => (
          <button key={r} type="button" aria-pressed={range === r} onClick={() => setRange(r)}>
            {t(`item.range${r}`)}
          </button>
        ))}
      </div>

      <div className="chart-card">
        {history.data ? (
          <PriceChart name={item.name} points={history.data.points} asOf={latest.data.asOf} rangeDays={range} baseline={item.baseline} />
        ) : (
          <LoadState loading={history.loading} error={history.error} onRetry={history.reload} />
        )}
      </div>

      <div className="stats">
        <div>
          <span>{t('item.low')}</span>
          <span>{stats ? pesoWhole(stats.low, lang) : '—'}</span>
        </div>
        <div>
          <span>{t('item.usual')}</span>
          <span>{item.baseline !== null ? pesoWhole(item.baseline, lang) : '—'}</span>
        </div>
        <div>
          <span>{t('item.high')}</span>
          <span>{stats ? pesoWhole(stats.high, lang) : '—'}</span>
        </div>
      </div>

      {suggestion !== null &&
        (inPlan ? (
          <Link to="/plan" className="button-secondary">
            {t('item.added', { qty: kg(inPlan.kg) })}
          </Link>
        ) : suggestion === 0 ? (
          <p className="notice">{t('item.skipAdvice', { pct: Math.abs(Math.trunc(item.pctVsBaseline ?? 0)) })}</p>
        ) : (
          <button
            type="button"
            className="button-primary"
            onClick={() => {
              setOverrides(withPick(overrides, category, item.id, suggestion));
              navigate('/plan');
            }}
          >
            {t('item.add', { qty: kg(suggestion) })}
          </button>
        ))}
    </div>
  );
}
