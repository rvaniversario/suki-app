import { Link } from 'react-router-dom';
import { useI18n, type TFunction } from '../i18n';
import { kg, pesoWhole } from '../lib/format';
import type { Plan } from '../lib/plan';
import type { Language } from '../lib/settings';

export function diffText(t: TFunction, plan: Plan, lang: Language): string {
  const d = Math.round(plan.diff);
  if (d === 0) return t('plan.same');
  return t(d < 0 ? 'plan.cheaper' : 'plan.pricier', { amount: pesoWhole(Math.abs(d), lang) });
}

export function planLine(t: TFunction, plan: Plan): string {
  return plan.rows.map((r) => t('plan.summaryItem', { name: r.item.name, qty: kg(r.kg) })).join(' · ');
}

/** Summary card. `variant` follows the layout: card (phone Plan), strip (tablet Today), side (desktop Today). */
export function PlanSummary({ plan, variant }: { plan: Plan; variant: 'card' | 'strip' | 'side' }) {
  const { t, lang } = useI18n();
  const total = (
    <>
      <span className="label">{variant === 'card' ? t('plan.total') : t('plan.title')}</span>
      <span className="total">{pesoWhole(plan.total, lang)}</span>
      <span className="diff">{diffText(t, plan, lang)}</span>
    </>
  );
  if (variant === 'card') return <div className="summary">{total}</div>;
  if (variant === 'strip') {
    return (
      <div className="summary strip">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>{total}</div>
        <div className="strip-right">
          <span className="diff">{planLine(t, plan)}</span>
          <Link className="summary-button" to="/plan">
            {t('plan.openPlan')}
          </Link>
        </div>
      </div>
    );
  }
  return (
    <div className="summary side-summary">
      {total}
      <span className="soft" style={{ marginTop: 8 }}>
        {planLine(t, plan)}
      </span>
      <Link className="summary-button" to="/plan" style={{ marginTop: 12 }}>
        {t('plan.openPlan')}
      </Link>
    </div>
  );
}
