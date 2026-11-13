import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useI18n } from '../i18n';
import { BackIcon } from '../components/Icons';
import { Sheet } from '../components/Sheet';
import { Stepper } from '../components/Stepper';
import { kg } from '../lib/format';
import { disableAlerts, enableAlerts, pushAvailability } from '../lib/push';
import { detectLanguage } from '../i18n';
import type { Language, Theme } from '../lib/settings';
import { CATEGORIES } from '../lib/types';
import { useAccount } from '../state/Account';
import { useApp } from '../state/AppState';
import { useUI } from '../state/UI';

function Segmented<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map(([v, text]) => (
        <button key={v} type="button" role="radio" aria-checked={value === v} onClick={() => onChange(v)}>
          {text}
        </button>
      ))}
    </div>
  );
}

function BudgetInput() {
  const { t } = useI18n();
  const { settings, update } = useApp();
  const [text, setText] = useState(settings.budget === null ? '' : String(settings.budget));
  useEffect(() => setText(settings.budget === null ? '' : String(settings.budget)), [settings.budget]);
  return (
    <section className="section">
      <label htmlFor="budget" className="section-title">
        {t('settings.budget')}
      </label>
      <div className="input-wrap money">
        <span className="affix" aria-hidden="true">
          ₱
        </span>
        <input
          id="budget"
          type="text"
          inputMode="numeric"
          autoComplete="off"
          placeholder={t('settings.budgetPlaceholder')}
          value={text}
          aria-describedby="budget-help"
          onChange={(e) => {
            const v = e.target.value.replace(/[^\d.]/g, '');
            setText(v);
            const n = parseFloat(v);
            update({ budget: v === '' || !Number.isFinite(n) ? null : n });
          }}
        />
      </div>
      <p id="budget-help" className="help">
        {t('settings.budgetHelp')}
      </p>
    </section>
  );
}

function AlertsRow() {
  const { t } = useI18n();
  const { settings, update, region, tracked } = useApp();
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const availability = pushAvailability();
  if (availability === 'unsupported') return null; // hidden where PushManager is unavailable

  const toggle = async () => {
    setMessage(null);
    if (settings.alerts) {
      setBusy(true);
      try {
        await disableAlerts();
      } finally {
        update({ alerts: false });
        setBusy(false);
      }
      return;
    }
    if (availability === 'ios-needs-install') return setMessage('settings.alertsIos');
    if (availability === 'not-configured') return setMessage('settings.alertsUnavailable');
    if (!region) return;
    setBusy(true);
    try {
      const res = await enableAlerts({
        region: region.id,
        trackedIds: [...tracked],
        language: settings.language ?? detectLanguage(),
      });
      if (res === 'denied') {
        update({ alerts: false });
        setMessage('settings.alertsDenied');
      } else update({ alerts: true });
    } catch {
      update({ alerts: false });
      setMessage('settings.alertsError');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel-row stack static">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <span className="label" id="alerts-label">
          {t('settings.alerts')}
          <small>{t('settings.alertsHelp')}</small>
        </span>
        <span className="switch-hit">
          <button
            type="button"
            role="switch"
            className="switch"
            aria-checked={settings.alerts}
            aria-labelledby="alerts-label"
            disabled={busy}
            onClick={toggle}
          />
        </span>
      </div>
      {message && (
        <p className="notice neutral" role="status">
          {t(message)}
        </p>
      )}
    </div>
  );
}

function AccountRow() {
  const { t } = useI18n();
  const account = useAccount();
  const [confirming, setConfirming] = useState(false);
  if (!account.enabled) {
    return (
      <div className="panel-row static">
        <span className="label">
          {t('settings.account')}
          <small>{t('settings.accountsUnavailable')}</small>
        </span>
      </div>
    );
  }
  if (!account.email) {
    return (
      <Link to="/signin" className="panel-row">
        <span className="label">
          {t('settings.account')}
          <small>{t('settings.accountHelp')}</small>
        </span>
        <span className="action">{t('settings.signIn')}</span>
      </Link>
    );
  }
  return (
    <div className="panel-row stack static">
      <span className="label">
        {t('settings.account')}
        <small>{account.email}</small>
      </span>
      {account.notice && (
        <p className="notice neutral" role="status">
          {t(account.notice)}
        </p>
      )}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button type="button" className="button-secondary" onClick={() => account.signOut()}>
          {t('settings.signOut')}
        </button>
        <button type="button" className="button-quiet button-danger" onClick={() => setConfirming(true)}>
          {t('settings.deleteAccount')}
        </button>
      </div>
      {confirming && (
        <Sheet label={t('settings.deleteAccount')} onClose={() => setConfirming(false)}>
          <h2>{t('settings.deleteAccount')}</h2>
          <p className="help">{t('settings.deleteConfirm')}</p>
          <button
            type="button"
            className="button-primary"
            onClick={async () => {
              await account.deleteAccount();
              setConfirming(false);
            }}
          >
            {t('settings.deleteYes')}
          </button>
          <button type="button" className="button-quiet" onClick={() => setConfirming(false)}>
            {t('settings.deleteNo')}
          </button>
        </Sheet>
      )}
    </div>
  );
}

export function Settings() {
  const { t } = useI18n();
  const { settings, update, region, tracked } = useApp();
  const { openRegionPicker } = useUI();
  const total = CATEGORIES.reduce((s, c) => s + settings.usualKg[c], 0);

  return (
    <div className="page narrow">
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <Link to="/" className="text-link" style={{ alignSelf: 'flex-start' }}>
          <BackIcon />
          {t('nav.today')}
        </Link>
        <h1 className="page-title">{t('settings.title')}</h1>
      </div>

      <section className="section">
        <h2 className="section-title">{t('settings.region')}</h2>
        <button type="button" className="panel-row card-link" onClick={openRegionPicker}>
          <span className="label">{region?.name ?? t('region.pick')}</span>
          <span className="action">{t('common.change')}</span>
        </button>
      </section>

      <section className="section">
        <h2 className="section-title">{t('settings.usual')}</h2>
        <div className="panel">
          {CATEGORIES.map((c) => {
            const name = t(`categories.${c}`);
            return (
              <div key={c} className="panel-row static">
                <span className="label">{name}</span>
                <Stepper
                  value={settings.usualKg[c]}
                  onChange={(v) => update({ usualKg: { ...settings.usualKg, [c]: v } })}
                  lessLabel={t('plan.lessAria', { name })}
                  moreLabel={t('plan.moreAria', { name })}
                  valueLabel={t('plan.qtyAria', { qty: kg(settings.usualKg[c]), name })}
                />
              </div>
            );
          })}
          <div className="panel-row static" style={{ minHeight: 48, fontSize: 14 }}>
            <span className="muted">{t('settings.total')}</span>
            <span style={{ fontWeight: 600 }}>{t('settings.perWeek', { kg: kg(total) })}</span>
          </div>
        </div>
      </section>

      <BudgetInput />

      <section className="section">
        <h2 className="section-title">{t('settings.goods')}</h2>
        <Link to="/settings/goods" className="panel-row card-link">
          <span className="label">{t('settings.goodsCount', { count: tracked.size })}</span>
          <span className="action">{t('settings.choose')}</span>
        </Link>
      </section>

      <section className="section">
        <h2 className="section-title">{t('settings.app')}</h2>
        <div className="panel">
          <div className="panel-row stack static">
            <span className="label">{t('settings.appearance')}</span>
            <Segmented<Theme>
              label={t('settings.appearance')}
              value={settings.theme}
              onChange={(theme) => update({ theme })}
              options={[
                ['system', t('settings.themeSystem')],
                ['light', t('settings.themeLight')],
                ['dark', t('settings.themeDark')],
              ]}
            />
          </div>
          <div className="panel-row stack static">
            <span className="label">{t('settings.language')}</span>
            <Segmented<Language>
              label={t('settings.language')}
              value={settings.language ?? detectLanguage()}
              onChange={(language) => update({ language })}
              options={[
                ['en', t('settings.langEn')],
                ['fil', t('settings.langFil')],
              ]}
            />
          </div>
          <AlertsRow />
          <AccountRow />
        </div>
      </section>

      <Link to="/privacy" className="text-link">
        {t('settings.privacy')}
      </Link>
    </div>
  );
}
