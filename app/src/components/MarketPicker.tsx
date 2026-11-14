import { useMemo, useState } from 'react';
import { useI18n } from '../i18n';
import { dateShort } from '../lib/format';
import { sortMarkets } from '../lib/markets';
import type { MarketIndex } from '../lib/types';
import { SearchBox } from '../screens/History';
import { Sheet } from './Sheet';

interface Props {
  index: MarketIndex;
  regionName: string;
  current: string | null;
  onChoose: (code: string | null) => void;
  onClose: () => void;
}

const NONE = '';

/** "My market": one market of the region, or none (regional prices only). Each shows its newest price date. */
export function MarketPicker({ index, regionName, current, onChoose, onClose }: Props) {
  const { t, lang } = useI18n();
  const [choice, setChoice] = useState<string>(current ?? NONE);
  const [q, setQ] = useState('');
  const all = useMemo(() => sortMarkets(index), [index]);
  const query = q.trim().toLowerCase();
  const shown = all.filter((m) => !query || m.name.toLowerCase().includes(query));
  const chosen = all.find((m) => m.code === choice) ?? null;

  return (
    <Sheet label={t('market.title')} onClose={onClose}>
      <form
        style={{ display: 'contents' }}
        onSubmit={(e) => {
          e.preventDefault();
          onChoose(choice || null);
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <h2>{t('market.title')}</h2>
          <p className="help">{t('market.body', { region: regionName })}</p>
        </div>
        {all.length > 8 && <SearchBox value={q} onChange={setQ} label={t('market.search')} />}
        <fieldset style={{ border: 0, margin: 0, padding: 0 }}>
          <legend className="visually-hidden">{t('market.title')}</legend>
          {!query && (
            <label className="radio-row">
              <input type="radio" name="market" value={NONE} checked={choice === NONE} onChange={() => setChoice(NONE)} />
              <span className="name">{t('market.none')}</span>
            </label>
          )}
          {shown.map((market) => (
            <label key={market.code} className="radio-row">
              <input type="radio" name="market" value={market.code} checked={choice === market.code} onChange={() => setChoice(market.code)} />
              <span className="name">{market.name}</span>
              <span className="tag">{market.latest ? dateShort(market.latest, lang) : t('market.noData')}</span>
            </label>
          ))}
          {shown.length === 0 && <p className="empty">{t('market.noResults', { q })}</p>}
        </fieldset>
        <button type="submit" className="button-primary">
          {chosen ? t('market.use', { market: chosen.name }) : t('market.useNone')}
        </button>
      </form>
    </Sheet>
  );
}
