import { STALE_AFTER_DAYS } from '../config';
import { useI18n } from '../i18n';
import { useOnline } from '../lib/data';
import { dateLong, daysSince } from '../lib/format';
import { Alert } from './Icons';

/** "As of" line, stale-data notice and offline notice for a report. */
export function ReportNotices({ asOf, source }: { asOf: string; source?: string }) {
  const { t, lang } = useI18n();
  const online = useOnline();
  const age = daysSince(asOf);
  const date = dateLong(asOf, lang);
  return (
    <>
      <p className="as-of">{t('today.asOf', { date, source: source ?? '' })}</p>
      {!online && (
        <p className="notice neutral" role="status">
          <Alert />
          {t('common.offline', { date })}
        </p>
      )}
      {age > STALE_AFTER_DAYS && (
        <p className="notice" role="status">
          <Alert />
          {t('today.stale', { days: age })}
        </p>
      )}
    </>
  );
}

export function LoadState({ loading, error, onRetry }: { loading: boolean; error: Error | null; onRetry: () => void }) {
  const { t } = useI18n();
  if (loading) return <p className="empty">{t('common.loading')}</p>;
  if (error) {
    return (
      <div className="empty" role="alert">
        <p style={{ margin: '0 0 8px' }}>{t('common.loadError')}</p>
        <button type="button" className="button-secondary" onClick={onRetry}>
          {t('common.retry')}
        </button>
      </div>
    );
  }
  return null;
}
