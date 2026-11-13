import { Link } from 'react-router-dom';
import { APP_NAME } from '../config';
import { useI18n } from '../i18n';
import { BackIcon } from '../components/Icons';

export function Privacy() {
  const { t } = useI18n();
  return (
    <div className="page narrow">
      <Link to="/settings" className="text-link" style={{ alignSelf: 'flex-start' }}>
        <BackIcon />
        {t('settings.title')}
      </Link>
      <h1 className="page-title">{t('privacy.title')}</h1>
      {['p1', 'p2', 'p3', 'p4', 'p5'].map((k) => (
        <p key={k} style={{ margin: 0, lineHeight: 1.5 }}>
          {t(`privacy.${k}`, { app: APP_NAME })}
        </p>
      ))}
    </div>
  );
}
