/* ==========================================================================
   app.js — entry point. Loaded as <script type="module" defer>, so it runs
   after parsing and never blocks first paint.
   ========================================================================== */

import {
  initNav, initHeader, initCart, initGate, initCatalog,
  initLedger, initForms, initPromo,
} from './ui.js';
import { initCheckout, initOrderStatus } from './checkout.js';

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
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot, { once: true });
} else {
  boot();
}
