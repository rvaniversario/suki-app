import { useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { useI18n } from '../i18n';
import { BackIcon } from '../components/Icons';
import { useAccount } from '../state/Account';

export function SignIn() {
  const { t } = useI18n();
  const account = useAccount();
  const [email, setEmail] = useState('');
  const [state, setState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');

  if (!account.enabled || account.email) return <Navigate to="/settings" replace />;

  return (
    <div className="page narrow">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <Link to="/settings" className="text-link" style={{ alignSelf: 'flex-start' }}>
          <BackIcon />
          {t('settings.title')}
        </Link>
        <h1 className="page-title">{t('signin.title')}</h1>
        <p className="page-subtitle">{t('signin.body')}</p>
      </div>

      <form
        className="section"
        onSubmit={async (e) => {
          e.preventDefault();
          setState('sending');
          try {
            await account.signInWithEmail(email.trim());
            setState('sent');
          } catch {
            setState('error');
          }
        }}
      >
        <label htmlFor="email" className="section-title">
          {t('signin.email')}
        </label>
        <div className="input-wrap">
          <input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <button type="submit" className="button-primary" disabled={state === 'sending'}>
          {t('signin.send')}
        </button>
        {state === 'sent' && (
          <p className="notice neutral" role="status">
            {t('signin.sent', { email })}
          </p>
        )}
        {state === 'error' && (
          <p className="notice" role="alert">
            {t('signin.error')}
          </p>
        )}
      </form>

      <p className="help" style={{ textAlign: 'center' }}>
        {t('signin.or')}
      </p>
      <button type="button" className="button-secondary" onClick={() => account.signInWithGoogle().catch(() => setState('error'))}>
        {t('signin.google')}
      </button>
      <Link to="/privacy" className="text-link">
        {t('signin.privacyLink')}
      </Link>
    </div>
  );
}
