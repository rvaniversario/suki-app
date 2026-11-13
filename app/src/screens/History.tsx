import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useI18n } from '../i18n';
import { SearchIcon } from '../components/Icons';
import { LoadState } from '../components/Notices';
import { StatusChip } from '../components/StatusChip';
import { peso } from '../lib/format';
import type { AnyCategory, LatestItem } from '../lib/types';
import { useApp } from '../state/AppState';

export const GROUP_ORDER: AnyCategory[] = ['fish', 'pork', 'chicken', 'beef', 'other'];

export function groupItems(items: LatestItem[], query: string): [AnyCategory, LatestItem[]][] {
  const q = query.trim().toLowerCase();
  const match = (i: LatestItem) => !q || i.name.toLowerCase().includes(q) || (i.detail ?? '').toLowerCase().includes(q);
  return GROUP_ORDER.map((c) => [c, items.filter((i) => i.category === c && match(i)).sort((a, b) => a.name.localeCompare(b.name))] as [AnyCategory, LatestItem[]]).filter(
    ([, list]) => list.length > 0,
  );
}

export function SearchBox({ value, onChange, label }: { value: string; onChange: (v: string) => void; label: string }) {
  return (
    <label className="input-wrap">
      <span className="muted" style={{ display: 'flex' }}>
        <SearchIcon />
      </span>
      <span className="visually-hidden">{label}</span>
      <input type="search" value={value} placeholder={label} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

export function History() {
  const { t, lang } = useI18n();
  const { latest, region } = useApp();
  const [q, setQ] = useState('');
  const groups = useMemo(() => groupItems(latest.data?.items ?? [], q), [latest.data, q]);

  return (
    <div className="page narrow">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, paddingTop: 8 }}>
        <h1 className="page-title">{t('history.title')}</h1>
        <p className="page-subtitle">{t('history.subtitle', { region: region?.name ?? '' })}</p>
      </div>
      <SearchBox value={q} onChange={setQ} label={t('history.search')} />
      {!latest.data ? (
        <LoadState loading={latest.loading} error={latest.error} onRetry={latest.reload} />
      ) : groups.length === 0 ? (
        <p className="empty">{t('history.noResults', { q })}</p>
      ) : (
        groups.map(([cat, items]) => (
          <section key={cat} className="section">
            <h2 className="section-title">{t(`categories.${cat}`)}</h2>
            <ul className="panel list">
              {items.map((i) => (
                <li key={i.id}>
                  <Link to={`/item/${i.id}`} className="panel-row">
                    <span className="label">
                      {i.name}
                      {i.detail && <small>{i.detail}</small>}
                    </span>
                    <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
                      <span className="price">{peso(i.price, lang)}</span>
                      {i.price !== null && <StatusChip item={i} />}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}
