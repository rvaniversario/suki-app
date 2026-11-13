/// <reference lib="webworker" />
import { clientsClaim } from 'workbox-core';
import { ExpirationPlugin } from 'workbox-expiration';
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching';
import { NavigationRoute, registerRoute } from 'workbox-routing';
import { StaleWhileRevalidate } from 'workbox-strategies';

declare const self: ServiceWorkerGlobalScope;

// registerType 'autoUpdate': take over as soon as a new version is installed.
self.skipWaiting();
clientsClaim();

// App shell and self-hosted fonts.
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

const base = new URL(self.registration.scope).pathname;

// Single-page app: every navigation gets index.html, so the app opens offline.
registerRoute(new NavigationRoute(createHandlerBoundToURL(`${base}index.html`), { denylist: [/\/data\//] }));

// Price data: show the last fetched prices instantly (and offline), refresh in the background.
registerRoute(
  ({ url }) => url.origin === self.location.origin && url.pathname.startsWith(`${base}data/`),
  new StaleWhileRevalidate({
    cacheName: 'price-data',
    plugins: [new ExpirationPlugin({ maxEntries: 400, maxAgeSeconds: 120 * 24 * 3600 })],
  }),
);

// ---------------------------------------------------------------- price drop alerts
interface PushPayload {
  title: string;
  body: string;
  url?: string;
  tag?: string;
}

self.addEventListener('push', (event) => {
  let data: PushPayload = { title: 'Suki', body: '' };
  try {
    data = { ...data, ...(event.data?.json() as PushPayload) };
  } catch {
    data.body = event.data?.text() ?? '';
  }
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      tag: data.tag,
      icon: `${base}icons/icon-192.png`,
      badge: `${base}icons/badge-72.png`,
      data: { url: base },
    }),
  );
});

// Clicking opens the app on Today (focusing an open window when there is one).
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = new URL(base, self.location.origin).href;
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      for (const w of windows) {
        if (w.url.startsWith(target) && 'focus' in w) {
          await w.navigate(target).catch(() => undefined);
          return w.focus();
        }
      }
      return self.clients.openWindow(target);
    })(),
  );
});
