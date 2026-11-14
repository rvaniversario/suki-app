/// <reference lib="webworker" />
/// <reference types="vite/client" />
// Workbox injects the precache manifest here at build time.
declare interface ServiceWorkerGlobalScope {
  __WB_MANIFEST: Array<import('workbox-precaching').PrecacheEntry | string>;
}
