import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { detectLanguage, I18nProvider, useI18n } from './i18n';
import { InstallSheet } from './components/InstallSheet';
import { Rail, Sidebar, TabBar } from './components/Nav';
import { MarketPicker } from './components/MarketPicker';
import { RegionPicker } from './components/RegionPicker';
import { countVisit, isIOS, isStandalone, shouldOfferInstall, snooze, type BeforeInstallPromptEvent } from './lib/install';
import { pushAvailability, updateAlerts } from './lib/push';
import type { Settings as SettingsT } from './lib/settings';
import { useApplyTheme } from './lib/theme';
import { Goods } from './screens/Goods';
import { History } from './screens/History';
import { Market } from './screens/Market';
import { Item } from './screens/Item';
import { Plan } from './screens/Plan';
import { Privacy } from './screens/Privacy';
import { Settings } from './screens/Settings';
import { SignIn } from './screens/SignIn';
import { Today } from './screens/Today';
import { AccountProvider } from './state/Account';
import { AppStateProvider, useApp } from './state/AppState';
import { UICtx, type UI } from './state/UI';

function useInstall() {
  const deferred = useRef<BeforeInstallPromptEvent | null>(null);
  const [canPrompt, setCanPrompt] = useState(false);
  const [open, setOpen] = useState(false);
  const [visits] = useState(countVisit);
  const [installed, setInstalled] = useState(isStandalone);

  useEffect(() => {
    const onPrompt = (e: Event) => {
      e.preventDefault();
      deferred.current = e as BeforeInstallPromptEvent;
      setCanPrompt(true);
    };
    const onInstalled = () => {
      setInstalled(true);
      setOpen(false);
    };
    window.addEventListener('beforeinstallprompt', onPrompt);
    window.addEventListener('appinstalled', onInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt);
      window.removeEventListener('appinstalled', onInstalled);
    };
  }, []);

  // Offer automatically after the second visit, never on the first load.
  useEffect(() => {
    if (shouldOfferInstall(visits, canPrompt)) {
      const id = setTimeout(() => setOpen(true), 1500);
      return () => clearTimeout(id);
    }
  }, [visits, canPrompt]);

  const prompt = useCallback(async () => {
    const e = deferred.current;
    if (!e) return;
    await e.prompt();
    const choice = await e.userChoice;
    deferred.current = null;
    setCanPrompt(false);
    setOpen(false);
    if (choice.outcome === 'dismissed') snooze();
  }, []);

  return {
    open,
    setOpen,
    canPrompt,
    installed,
    prompt,
    notNow: () => {
      snooze();
      setOpen(false);
    },
  };
}

function Shell() {
  const app = useApp();
  const { settings, update, regions, region, tracked } = app;
  const { t } = useI18n();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [marketPickerOpen, setMarketPickerOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const install = useInstall();

  // Ask the browser not to evict our data, once.
  useEffect(() => {
    if (app.firstRun) navigator.storage?.persist?.().catch(() => {});
  }, [app.firstRun]);

  // Region picker shows on first launch (or when the saved region is no longer available).
  const needsRegion = Boolean(regions.data) && !region;

  // Keep the push subscription row in step with region, tracked goods and language.
  const lang = settings.language ?? detectLanguage();
  const trackedKey = [...tracked].sort().join(',');
  useEffect(() => {
    if (!settings.alerts || !region || pushAvailability() !== 'available') return;
    const id = setTimeout(() => {
      updateAlerts({ region: region.id, trackedIds: trackedKey ? trackedKey.split(',') : [], language: lang }).catch(() => {});
    }, 2000);
    return () => clearTimeout(id);
  }, [settings.alerts, region, trackedKey, lang]);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(id);
  }, [toast]);

  const ui: UI = useMemo(
    () => ({
      openRegionPicker: () => setPickerOpen(true),
      openMarketPicker: () => setMarketPickerOpen(true),
      openInstall: install.installed ? null : () => startInstall(install),
      toast: setToast,
    }),
    [install],
  );

  return (
    <UICtx.Provider value={ui}>
      <a className="skip-link" href="#main">
        {t('common.skipToContent')}
      </a>
      <div className="shell">
        <Rail />
        <Sidebar onInstall={ui.openInstall} />
        <main id="main" className="main">
          <Routes>
            <Route path="/" element={<Today />} />
            <Route path="/plan" element={<Plan />} />
            <Route path="/history" element={<History />} />
            <Route path="/item/:id" element={<Item />} />
            <Route path="/market" element={<Market />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/settings/goods" element={<Goods />} />
            <Route path="/signin" element={<SignIn />} />
            <Route path="/privacy" element={<Privacy />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        <TabBar />
      </div>
      {(pickerOpen || needsRegion) && regions.data && (
        <RegionPicker
          regions={regions.data}
          current={settings.region}
          onChoose={(id) => {
            if (id !== settings.region) update({ region: id });
            setPickerOpen(false);
          }}
          onClose={needsRegion ? undefined : () => setPickerOpen(false)}
        />
      )}
      {marketPickerOpen && region && app.markets.data && (
        <MarketPicker
          index={app.markets.data}
          regionName={region.name}
          current={app.market?.code ?? null}
          onChoose={(code) => {
            app.setMarket(code);
            setMarketPickerOpen(false);
          }}
          onClose={() => setMarketPickerOpen(false)}
        />
      )}
      {install.open && !pickerOpen && !marketPickerOpen && !needsRegion && (
        <InstallSheet onInstall={install.canPrompt ? install.prompt : null} ios={isIOS()} onNotNow={install.notNow} />
      )}
      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </UICtx.Provider>
  );
}

/** Chromium: native prompt straight away. Elsewhere: our sheet with instructions. */
function startInstall(install: ReturnType<typeof useInstall>) {
  if (install.canPrompt) install.prompt();
  else install.setOpen(true);
}

function Localised() {
  const { settings } = useApp();
  const lang = settings.language ?? detectLanguage();
  useApplyTheme(settings.theme);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  return (
    <I18nProvider lang={lang}>
      <AccountProvider>
        <Shell />
      </AccountProvider>
    </I18nProvider>
  );
}

export function App({ initialSettings }: { initialSettings?: SettingsT }) {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, '') || undefined}>
      <AppStateProvider initial={initialSettings}>
        <Localised />
      </AppStateProvider>
    </BrowserRouter>
  );
}
