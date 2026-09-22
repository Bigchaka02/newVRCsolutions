/* ==========================================================================
   ui.js — interactive components.
   Every behaviour here is a response to a user action. There is no
   scroll-triggered animation: content is visible in the HTML from the start,
   which keeps the page usable without JS and avoids layout shift.
   ========================================================================== */

import * as cart from './store.js';
import { api } from './api.js';

// Site root, e.g. "" on the real domain or "/newVRCsolutions" on GitHub Pages.
export const ROOT = new URL('../../', import.meta.url).pathname.replace(/\/$/, '');

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

/* ---------- toast -------------------------------------------------------- */

let toastTimer;
export function toast(message) {
  let el = $('#toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'toast';
    el.className = 'toast';
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.dataset.open = 'true';
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.dataset.open = 'false'; }, 2600);
}

/* ---------- focus trap --------------------------------------------------- */

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])';

function trapFocus(container, event) {
  const nodes = $$(FOCUSABLE, container).filter((n) => n.offsetParent !== null);
  if (!nodes.length) return;
  const first = nodes[0];
  const last = nodes[nodes.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

/* ---------- mobile nav --------------------------------------------------- */

export function initNav() {
  const burger = $('#burger');
  const panel = $('#mobile-nav');
  if (!burger || !panel) return;

  burger.addEventListener('click', () => {
    const open = panel.dataset.open === 'true';
    panel.dataset.open = String(!open);
    burger.setAttribute('aria-expanded', String(!open));
  });

  // Mark the current page so people know where they are.
  const here = location.pathname.replace(/index\.html$/, '').replace(/\/$/, '') || '/';
  $$('.nav a, .mobile-nav a').forEach((a) => {
    const target = new URL(a.getAttribute('href'), location.origin).pathname
      .replace(/index\.html$/, '').replace(/\/$/, '') || '/';
    if (target === here) a.setAttribute('aria-current', 'page');
  });
}

/* ---------- cart drawer -------------------------------------------------- */

let lastFocused = null;

export function initCart() {
  const drawer = $('#cart-drawer');
  const scrim = $('#scrim');
  if (!drawer || !scrim) return;

  const open = () => {
    lastFocused = document.activeElement;
    drawer.dataset.open = 'true';
    scrim.dataset.open = 'true';
    drawer.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    const target = $(FOCUSABLE, drawer);
    if (target) target.focus();
  };

  const close = () => {
    drawer.dataset.open = 'false';
    scrim.dataset.open = 'false';
    drawer.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    if (lastFocused) lastFocused.focus();
  };

  $$('[data-cart-open]').forEach((b) => b.addEventListener('click', open));
  $$('[data-cart-close]').forEach((b) => b.addEventListener('click', close));
  scrim.addEventListener('click', close);

  document.addEventListener('keydown', (e) => {
    if (drawer.dataset.open !== 'true') return;
    if (e.key === 'Escape') close();
    if (e.key === 'Tab') trapFocus(drawer, e);
  });

  // Add-to-cart, delegated so it also covers cards rendered after load.
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-add]');
    if (!btn) return;
    e.preventDefault();
    let product;
    try {
      product = JSON.parse(btn.dataset.add);
    } catch {
      return;
    }
    const qtyInput = btn.dataset.qtyFrom ? $('#' + btn.dataset.qtyFrom) : null;
    const qty = qtyInput ? Number(qtyInput.value) || 1 : 1;
    cart.add(product, qty);
    toast(`${product.name} added to cart`);
    if (btn.dataset.openAfter !== 'false') open();
  });

  cart.subscribe(render);
  window.vrcOpenCart = open;
}

function render(state) {
  const totals = cart.totals();
  const n = cart.count();

  $$('[data-cart-count]').forEach((el) => {
    el.textContent = String(n);
    el.dataset.empty = String(n === 0);
  });
  $$('[data-cart-total]').forEach((el) => { el.textContent = cart.money(totals.total); });

  const body = $('#cart-lines');
  const foot = $('#cart-foot');
  if (!body) return;

  if (!state.items.length) {
    body.innerHTML = `
      <div class="empty-state">
        <p>Your cart is empty.</p>
        <a class="btn btn-primary" href="${ROOT}/shop/">Browse the catalog</a>
      </div>`;
    if (foot) foot.hidden = true;
    return;
  }

  if (foot) foot.hidden = false;

  body.innerHTML = state.items.map((i) => `
    <div class="line">
      <div class="line-media">${
        i.image
          ? `<img src="${esc(i.image)}" alt="" loading="lazy" width="62" height="78">`
          : ''
      }</div>
      <div>
        <div class="line-name">${esc(i.name)}</div>
        <div class="line-sku mono">${esc(i.sku)}</div>
        <div class="line-qty">
          <button type="button" data-dec="${esc(i.sku)}" aria-label="Decrease quantity of ${esc(i.name)}">&minus;</button>
          <span>${i.qty}</span>
          <button type="button" data-inc="${esc(i.sku)}" aria-label="Increase quantity of ${esc(i.name)}">+</button>
        </div>
      </div>
      <div>
        <div class="line-price">${cart.money(i.price * i.qty)}</div>
        <button type="button" class="line-remove" data-remove="${esc(i.sku)}">Remove</button>
      </div>
    </div>`).join('');

  body.onclick = (e) => {
    const inc = e.target.closest('[data-inc]');
    const dec = e.target.closest('[data-dec]');
    const rm = e.target.closest('[data-remove]');
    if (inc) {
      const it = state.items.find((x) => x.sku === inc.dataset.inc);
      cart.setQty(inc.dataset.inc, it.qty + 1);
    }
    if (dec) {
      const it = state.items.find((x) => x.sku === dec.dataset.dec);
      cart.setQty(dec.dataset.dec, it.qty - 1);
    }
    if (rm) cart.remove(rm.dataset.remove);
  };

  // Free-shipping progress: a real state readout, not ornament.
  const meter = $('#ship-meter');
  if (meter) {
    const pct = Math.min(100, (totals.subtotal - totals.discount) / cart.CONFIG.freeShippingThreshold * 100);
    const fill = $('.ship-fill', meter);
    const label = $('p', meter);
    fill.style.width = pct + '%';
    fill.dataset.full = String(totals.shipping === 0);
    label.textContent = totals.shipping === 0
      ? 'Free shipping applied.'
      : `${cart.money(totals.remainingForFreeShipping)} more for free shipping.`;
  }

  const t = $('#cart-totals');
  if (t) {
    t.innerHTML = `
      <div><span>Subtotal</span><span>${cart.money(totals.subtotal)}</span></div>
      ${totals.discount > 0
        ? `<div><span>Discount (${esc(state.promo)})</span><span>&minus;${cart.money(totals.discount)}</span></div>`
        : ''}
      <div><span>Shipping</span><span>${totals.shipping === 0 ? 'Free' : cart.money(totals.shipping)}</span></div>
      <div class="grand"><span>Total</span><span>${cart.money(totals.total)}</span></div>`;
  }
}

/* ---------- promo field -------------------------------------------------- */

export function initPromo() {
  const form = $('#promo-form');
  if (!form) return;
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const input = $('#promo-input', form);
    const msg = $('#promo-msg', form);
    if (cart.applyPromo(input.value)) {
      msg.textContent = `${cart.CONFIG.promoPercent}% discount applied.`;
      msg.className = 'hint';
      input.value = '';
    } else {
      msg.textContent = "That code isn't recognised. Check the spelling and try again.";
      msg.className = 'err';
    }
  });
}

/* ---------- RUO gate ----------------------------------------------------- */
/* Overlays already-rendered content. Crawlers, no-JS visitors and screen
   readers all receive the full page; only the overlay is conditional. */

export function initGate() {
  const gate = $('#ruo-gate');
  if (!gate) return;
  // Legal pages opt out: people must be able to read what they're agreeing to.
  if (document.body.dataset.gate === 'off') return;
  if (cart.hasAck()) return;

  const form = $('#gate-form', gate);
  const enter = $('#gate-enter', gate);
  const boxes = $$('input[type="checkbox"]', gate);

  const sync = () => {
    const all = boxes.every((b) => b.checked);
    enter.disabled = !all;
    boxes.forEach((b) => { b.closest('.check').dataset.checked = String(b.checked); });
  };

  boxes.forEach((b) => b.addEventListener('change', sync));
  sync();

  gate.dataset.open = 'true';
  document.body.style.overflow = 'hidden';
  setTimeout(() => { const f = $(FOCUSABLE, gate); if (f) f.focus(); }, 40);

  document.addEventListener('keydown', (e) => {
    if (gate.dataset.open === 'true' && e.key === 'Tab') trapFocus(gate, e);
  });

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    cart.setAck();
    gate.dataset.open = 'false';
    document.body.style.overflow = '';

    // Fire-and-forget compliance record. A failed call never blocks entry —
    // the localStorage flag is what the UI reads.
    api('/api/compliance/ruo-ack', {
      method: 'POST',
      body: { path: location.pathname, at: new Date().toISOString() },
      keepalive: true,
    }).catch(() => {});
  });
}

/* ---------- catalog filtering -------------------------------------------- */
/* Filters the 22 products already present in the HTML. No refetch, no
   pagination, no layout shift — the markup is the source of truth. */

export function initCatalog() {
  const root = $('#catalog');
  if (!root) return;

  const cards = $$('[data-product]', root);
  const chips = $$('.chip[data-filter]');
  const search = $('#catalog-search');
  const sort = $('#catalog-sort');
  const countEl = $('#catalog-count');
  const empty = $('#catalog-empty');

  let category = 'all';

  const apply = () => {
    const q = (search?.value || '').trim().toLowerCase();
    let shown = 0;

    cards.forEach((card) => {
      const d = card.dataset;
      const matchCat = category === 'all' || d.category === category;
      const haystack = `${d.name} ${d.sku} ${d.compound} ${d.lot}`.toLowerCase();
      const matchQ = !q || haystack.includes(q);
      const visible = matchCat && matchQ;
      card.hidden = !visible;
      if (visible) shown++;
    });

    if (countEl) {
      countEl.textContent = shown === cards.length
        ? `${shown} products`
        : `${shown} of ${cards.length} products`;
    }
    if (empty) empty.hidden = shown !== 0;
  };

  const reorder = (mode) => {
    const sorted = [...cards].sort((a, b) => {
      const ap = Number(a.dataset.price);
      const bp = Number(b.dataset.price);
      if (mode === 'price-asc') return ap - bp;
      if (mode === 'price-desc') return bp - ap;
      if (mode === 'name') return a.dataset.name.localeCompare(b.dataset.name);
      return Number(a.dataset.order) - Number(b.dataset.order);
    });
    sorted.forEach((c) => root.appendChild(c));
  };

  const select = (value, updateHash) => {
    const chip = chips.find((c) => c.dataset.filter === value) || chips[0];
    category = chip.dataset.filter;
    chips.forEach((c) => c.setAttribute('aria-pressed', String(c === chip)));
    if (updateHash) {
      history.replaceState(null, '', category === 'all' ? location.pathname : `#${category}`);
    }
    apply();
  };

  chips.forEach((chip) => chip.addEventListener('click', () => select(chip.dataset.filter, true)));
  window.addEventListener('hashchange', () => select(location.hash.slice(1) || 'all', false));
  if (location.hash) select(location.hash.slice(1), false);

  search?.addEventListener('input', debounce(apply, 120));
  sort?.addEventListener('change', () => { reorder(sort.value); apply(); });

  apply();
}

/* ---------- hero ledger search ------------------------------------------- */

export function initLedger() {
  const table = $('#ledger-table');
  if (!table) return;
  const input = $('#ledger-search');
  const rows = $$('tbody tr', table);
  const empty = $('#ledger-empty');
  const countEl = $('#ledger-count');

  const run = () => {
    const q = (input?.value || '').trim().toLowerCase();
    let shown = 0;
    rows.forEach((row) => {
      const hit = !q || row.dataset.search.includes(q);
      row.hidden = !hit;
      if (hit) shown++;
    });
    if (empty) empty.hidden = shown !== 0;
    if (countEl) countEl.textContent = `${shown} ${shown === 1 ? 'batch' : 'batches'} on file`;
  };

  const preset = new URLSearchParams(location.search).get('q');
  if (preset && input) input.value = preset;

  input?.addEventListener('input', debounce(run, 110));
  run();
}

/* ---------- forms -------------------------------------------------------- */

export function initForms() {
  $$('form[data-api]').forEach((form) => {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const status = $('[data-status]', form);
      const submit = $('button[type="submit"]', form);
      const payload = Object.fromEntries(new FormData(form).entries());

      submit.disabled = true;
      const original = submit.textContent;
      submit.textContent = 'Sending…';
      if (status) { status.textContent = ''; status.className = 'hint'; }

      try {
        if (!form.reportValidity()) throw new Error('Fill in the highlighted fields');
        await api(form.dataset.api, { method: 'POST', body: payload });
        form.reset();
        if (status) {
          status.textContent = form.dataset.success || 'Sent. We reply within one business day.';
          status.className = 'hint';
        }
      } catch (err) {
        if (status) {
          // Say what happened and what to do about it — no apology, no vagueness.
          status.textContent = `${err.message}. Email ${form.dataset.fallback || 'hello@vrcsolutions.co'} if this keeps happening.`;
          status.className = 'err';
        }
      } finally {
        submit.disabled = false;
        submit.textContent = original;
      }
    });
  });

  // Quantity steppers on product pages.
  $$('.qty').forEach((group) => {
    const input = $('input', group);
    $('[data-step="-1"]', group)?.addEventListener('click', () => {
      input.value = Math.max(1, Number(input.value) - 1);
    });
    $('[data-step="1"]', group)?.addEventListener('click', () => {
      input.value = Math.min(99, Number(input.value) + 1);
    });
  });
}

/* ---------- helpers ------------------------------------------------------ */

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

export function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}
