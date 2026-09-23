/* ==========================================================================
   app.js — entry point. Loaded as <script type="module" defer>, so it runs
   after parsing and never blocks first paint.
   ========================================================================== */

import {
  initNav, initHeader, initCart, initGate, initCatalog,
  initLedger, initForms, initPromo,
} from './ui.js';
import { initCheckout, initOrderStatus } from './checkout.js';
import { initFx } from './fx.js';

function boot() {
  // Each initialiser no-ops when its markup is absent, so one bundle serves
  // every page without per-page conditionals.
  initNav();
  initHeader();
  initCart();
  initGate();
  initCatalog();
  initLedger();
  initForms();
  initPromo();
  initCheckout();
  initOrderStatus();
  // Motion last, so it decorates markup the initialisers above have settled.
  try { initFx(); } catch (err) { console.error('[fx]', err); }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot, { once: true });
} else {
  boot();
}
