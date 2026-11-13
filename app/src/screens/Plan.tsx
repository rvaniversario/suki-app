import { Link } from 'react-router-dom';
import { useI18n } from '../i18n';
import { LoadState, ReportNotices } from '../components/Notices';
import { PlanSummary } from '../components/PlanSummary';
import { StatusChip } from '../components/StatusChip';
import { Stepper } from '../components/Stepper';
import { kg, peso, pesoWhole } from '../lib/format';
import { withQty } from '../lib/planStore';
import { CATEGORIES } from '../lib/types';
import { useApp } from '../state/AppState';

export function Plan() {
  const { t, lang } = useI18n();
  const { plan, latest, region, settings, overrides, setOverrides } = useApp();
  const usualTotal = CATEGORIES.reduce((s, c) => s + settings.usualKg[c], 0);
  const maxKg = Math.max(0, ...(plan?.rows.map((r) => r.kg) ?? []));
  const changed = Object.keys(overrides.qty ?? {}).length > 0 || Object.keys(overrides.picks ?? {}).length > 0;

  return (
    <div className="page narrow">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, paddingTop: 8 }}>
        <h1 className="page-title">{t('plan.title')}</h1>
        <p className="page-subtitle">{t('plan.subtitle', { kg: kg(usualTotal) })}</p>
      </div>

      {!plan || !latest.data ? (
        <LoadState loading={latest.loading} error={latest.error} onRetry={latest.reload} />
      ) : plan.rows.length === 0 ? (
        <p className="empty">{t('plan.empty')}</p>
      ) : (
        <>
          <PlanSummary plan={plan} variant="card" />
          {plan.trimmed && settings.budget !== null && (
            <p className="notice neutral" role="status">
              {t('plan.trimmed', { budget: pesoWhole(settings.budget, lang) })}
            </p>
          )}
          {plan.overBudget !== null && (
            <p className="notice" role="status">
              {t('plan.overBudget', { amount: pesoWhole(plan.overBudget, lang) })}
            </p>
          )}
          {plan.rows.map((row) => {
            const name = row.item.name;
            return (
              <section key={row.category} className="plan-card" aria-label={t(`categories.${row.category}`)}>
                <div className="head">
                  <div className="meta">
                    <span className="kicker">
                      {t(`categories.${row.category}`)} · {t(`plan.advice.${row.advice}`)}
                      {row.manual && ` · ${t('plan.changed')}`}
                    </span>
                    <Link to={`/item/${row.item.id}`} className="name">
                      {name}
                    </Link>
                    {row.kg > 0 ? (
                      <span className="detail">
                        {t('plan.lineCost', { price: peso(row.item.price, lang), cost: pesoWhole(row.cost, lang) })}
                      </span>
                    ) : (
                      <span>
                        <StatusChip item={row.item} />
                      </span>
                    )}
                  </div>
                  <Stepper
                    value={row.kg}
                    onChange={(v) => setOverrides(withQty(overrides, row.category, v))}
                    lessLabel={t('plan.lessAria', { name })}
                    moreLabel={t('plan.moreAria', { name })}
                    valueLabel={t('plan.qtyAria', { qty: kg(row.kg), name })}
                  />
                </div>
                <div className="bar" aria-hidden="true">
                  <div style={{ width: `${maxKg ? (row.kg / maxKg) * 100 : 0}%` }} />
                </div>
              </section>
            );
          })}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0 20px' }}>
            <Link to="/settings" className="text-link">
              {t('plan.editSettings')}
            </Link>
            {changed && (
              <button type="button" className="text-link" onClick={() => setOverrides({ picks: {}, qty: {} })}>
                {t('plan.reset')}
              </button>
            )}
          </div>
          <ReportNotices asOf={latest.data.asOf} source={region?.source} />
        </>
      )}
    </div>
  );
}
