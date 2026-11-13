import { Link, NavLink, useLocation } from 'react-router-dom';
import { APP_NAME } from '../config';
import { useI18n } from '../i18n';
import { HistoryIcon, PlanIcon, SettingsIcon, TodayIcon } from './Icons';

const LINKS = [
  { to: '/', key: 'nav.today', Icon: TodayIcon, end: true },
  { to: '/plan', key: 'nav.plan', Icon: PlanIcon, end: false },
  { to: '/history', key: 'nav.history', Icon: HistoryIcon, end: false },
] as const;

function isActive(path: string, to: string, end: boolean): boolean {
  if (to === '/history' && path.startsWith('/item/')) return true; // item screens live under History
  return end ? path === to : path === to || path.startsWith(`${to}/`);
}

function Links({ size }: { size?: number }) {
  const { t } = useI18n();
  const { pathname } = useLocation();
  return (
    <>
      {LINKS.map(({ to, key, Icon, end }) => (
        <Link key={to} to={to} aria-current={isActive(pathname, to, end) ? 'page' : undefined}>
          <Icon size={size} />
          {t(key)}
        </Link>
      ))}
    </>
  );
}

export function TabBar() {
  const { t } = useI18n();
  return (
    <nav className="tabbar" aria-label={t('nav.main')}>
      <Links />
    </nav>
  );
}

export function Rail() {
  const { t } = useI18n();
  return (
    <nav className="rail" aria-label={t('nav.main')}>
      <div className="brand-mark" aria-hidden="true">
        {APP_NAME[0]}
      </div>
      <Links />
      <NavLink to="/settings" className="bottom">
        <SettingsIcon size={22} />
        {t('nav.settings')}
      </NavLink>
    </nav>
  );
}

export function Sidebar({ onInstall }: { onInstall: (() => void) | null }) {
  const { t } = useI18n();
  return (
    <nav className="sidebar" aria-label={t('nav.main')}>
      <div className="brand">
        <div className="brand-mark" aria-hidden="true">
          {APP_NAME[0]}
        </div>
        <span className="app-name">{APP_NAME}</span>
      </div>
      <Links size={20} />
      {onInstall && (
        <button type="button" className="install" onClick={onInstall}>
          {t('nav.installApp')}
        </button>
      )}
      <NavLink to="/settings" className="bottom">
        <SettingsIcon />
        {t('nav.settings')}
      </NavLink>
    </nav>
  );
}
