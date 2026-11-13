import { useState } from 'react';
import { useI18n } from '../i18n';
import type { Region } from '../lib/types';
import { Sheet } from './Sheet';

interface Props {
  regions: Region[];
  current: string | null;
  onChoose: (id: string) => void;
  onClose?: () => void;
}

export function RegionPicker({ regions, current, onChoose, onClose }: Props) {
  const { t } = useI18n();
  const available = regions.filter((r) => r.status === 'daily');
  const [choice, setChoice] = useState<string | null>(current ?? available[0]?.id ?? null);
  const chosen = regions.find((r) => r.id === choice);

  return (
    <Sheet label={t('region.title')} onClose={onClose}>
      <form
        style={{ display: 'contents' }}
        onSubmit={(e) => {
          e.preventDefault();
          if (choice) onChoose(choice);
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <h2>{t('region.title')}</h2>
          <p className="help">{t('region.body')}</p>
        </div>
        <fieldset style={{ border: 0, margin: 0, padding: 0 }}>
          <legend className="visually-hidden">{t('region.title')}</legend>
          {regions.map((r) => {
            const disabled = r.status !== 'daily';
            return (
              <label key={r.id} className={`radio-row${disabled ? ' disabled' : ''}`}>
                <input
                  type="radio"
                  name="region"
                  value={r.id}
                  disabled={disabled}
                  checked={choice === r.id}
                  onChange={() => setChoice(r.id)}
                />
                <span className="name">{r.name}</span>
                <span className="tag">{disabled ? t('region.unavailable') : t('region.daily')}</span>
              </label>
            );
          })}
        </fieldset>
        <button type="submit" className="button-primary" disabled={!chosen}>
          {chosen ? t('region.use', { region: chosen.name }) : t('region.pick')}
        </button>
      </form>
    </Sheet>
  );
}
