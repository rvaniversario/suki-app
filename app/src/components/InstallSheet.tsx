import { APP_NAME } from '../config';
import { useI18n } from '../i18n';
import { Check, ShareIcon } from './Icons';
import { Sheet } from './Sheet';

interface Props {
  /** Chromium: trigger the captured beforeinstallprompt. Null on iOS / unsupported browsers. */
  onInstall: (() => void) | null;
  ios: boolean;
  onNotNow: () => void;
}

export function InstallSheet({ onInstall, ios, onNotNow }: Props) {
  const { t } = useI18n();
  const title = t('install.title', { app: APP_NAME });
  return (
    <Sheet label={title} onClose={onNotNow}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <div className="brand-mark" aria-hidden="true" style={{ width: 60, height: 60, flex: 'none', borderRadius: 14, fontSize: 30 }}>
          {APP_NAME[0]}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <h2>{title}</h2>
          <span className="help">{t('install.subtitle')}</span>
        </div>
      </div>
      <ul className="benefits">
        <li>
          <Check />
          {t('install.benefitFullScreen')}
        </li>
        <li>
          <Check />
          {t('install.benefitOffline')}
        </li>
      </ul>
      {ios ? (
        <ol className="benefits" style={{ listStyle: 'none' }}>
          <li>
            <ShareIcon />
            {t('install.iosStep1')}
          </li>
          <li>
            <span aria-hidden="true" style={{ width: 18, textAlign: 'center', fontWeight: 700 }}>
              +
            </span>
            {t('install.iosStep2')}
          </li>
        </ol>
      ) : (
        !onInstall && <p className="help">{t('install.manual')}</p>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {onInstall && !ios && (
          <button type="button" className="button-primary" onClick={onInstall}>
            {t('install.add')}
          </button>
        )}
        <button type="button" className="button-quiet" onClick={onNotNow}>
          {ios || !onInstall ? t('install.gotIt') : t('install.notNow')}
        </button>
      </div>
    </Sheet>
  );
}
