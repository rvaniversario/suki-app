import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useI18n } from '../i18n';
import { BackIcon } from '../components/Icons';
import { LoadState } from '../components/Notices';
import { featuredIds, useApp } from '../state/AppState';
import { groupItems, SearchBox } from './History';

export function Goods() {
  const { t } = useI18n();
  const { latest, tracked, settings, update } = useApp();
  const [q, setQ] = useState('');
  const groups = useMemo(() => groupItems(latest.data?.items ?? [], q), [latest.data, q]);

  const toggle = (id: string, on: boolean) => {
    const next = new Set(tracked);
    if (on) next.add(id);
    else next.delete(id);
    update({ trackedIds: [...next].sort() });
  };

  return (
    <div className="page narrow">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <Link to="/settings" className="text-link" style={{ alignSelf: 'flex-start' }}>
          <BackIcon />
          {t('settings.title')}
        </Link>
        <h1 className="page-title">{t('goods.title')}</h1>
        <p className="page-subtitle" aria-live="polite">
          {t('goods.subtitle', { count: tracked.size })}
        </p>
      </div>
      <SearchBox value={q} onChange={setQ} label={t('goods.search')} />
      {settings.trackedIds !== null && latest.data && (
        <button
          type="button"
          className="text-link"
          style={{ alignSelf: 'flex-start' }}
          onClick={() => update({ trackedIds: null })}
          title={featuredIds(latest.data.items).join(', ')}
        >
          {t('goods.reset')}
        </button>
      )}
      {!latest.data ? (
        <LoadState loading={latest.loading} error={latest.error} onRetry={latest.reload} />
      ) : groups.length === 0 ? (
        <p className="empty">{t('goods.noResults', { q })}</p>
      ) : (
        groups.map(([cat, items]) => (
          <fieldset key={cat} className="section" style={{ border: 0, margin: 0, padding: 0 }}>
            <legend className="section-title" style={{ marginBottom: 6 }}>
              {t(`categories.${cat}`)}
            </legend>
            <ul className="panel list">
              {items.map((i) => (
                <li key={i.id}>
                  <label className="check-row">
                    <input type="checkbox" checked={tracked.has(i.id)} onChange={(e) => toggle(i.id, e.target.checked)} />
                    <span className="label" style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontWeight: 600 }}>{i.name}</span>
                      {i.detail && <span className="detail">{i.detail}</span>}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </fieldset>
        ))
      )}
    </div>
  );
}
