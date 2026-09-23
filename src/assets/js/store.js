/* ==========================================================================
   store.js — cart state, persistence, and client-side price preview.
   --------------------------------------------------------------------------
   IMPORTANT: totals computed here are a PREVIEW ONLY. The server recomputes
   every figure in POST /api/orders from its own catalog before an order is
   accepted. Never trust a price that arrived from the browser.
   ========================================================================== */

const KEY = 'vrc.cart.v1';
const ACK_KEY = 'vrc.ruo-ack.v1';
const ACK_DAYS = 30;

export const CONFIG = {
  freeShippingThreshold: 105.0,
  flatShipping: 9.95,
  promoCode: 'FIRST15',
  promoPercent: 15,
};

/* ---------- persistence -------------------------------------------------- */

/** localStorage throws in private-mode Safari and when storage is full.
 *  Every access is guarded; an unavailable store degrades to an empty cart. */
function read() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { items: [], promo: null };
    const parsed = JSON.parse(raw);
    return {
      items: Array.isArray(parsed.items) ? parsed.items : [],
      promo: typeof parsed.promo === 'string' ? parsed.promo : null,
    };
  } catch {
    return { items: [], promo: null };
  }
}

function write(state) {
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* Quota or private mode — cart stays in memory for this session only. */
  }
}

let state = read();
const listeners = new Set();

function emit() {
  write(state);
  listeners.forEach((fn) => {
    try { fn(state); } catch (err) { console.error('[cart listener]', err); }
  });
}

export function subscribe(fn) {
  listeners.add(fn);
  fn(state);
  return () => listeners.delete(fn);
}

/* ---------- mutations ---------------------------------------------------- */

export function getState() {
  return { items: state.items.map((i) => ({ ...i })), promo: state.promo };
}

export function add(product, qty = 1) {
  const n = clampQty(qty);
  const existing = state.items.find((i) => i.sku === product.sku);
  if (existing) {
    existing.qty = clampQty(existing.qty + n);
  } else {
    state.items.push({
      sku: product.sku,
      slug: product.slug,
      name: product.name,
      price: Number(product.price),
      image: product.image || '',
      qty: n,
    });
  }
  emit();
}

export function setQty(sku, qty) {
  const item = state.items.find((i) => i.sku === sku);
  if (!item) return;
  const n = clampQty(qty);
  if (n <= 0) return remove(sku);
  item.qty = n;
  emit();
}

export function remove(sku) {
  state.items = state.items.filter((i) => i.sku !== sku);
  emit();
}

export function clear() {
  state = { items: [], promo: null };
  emit();
}

export function applyPromo(code) {
  const normalised = String(code || '').trim().toUpperCase();
  if (normalised !== CONFIG.promoCode) return false;
  state.promo = normalised;
  emit();
  return true;
}

function clampQty(n) {
  const v = Math.floor(Number(n));
  if (!Number.isFinite(v)) return 1;
  return Math.max(0, Math.min(99, v));
}

/* ---------- derived ------------------------------------------------------ */

export function count() {
  return state.items.reduce((sum, i) => sum + i.qty, 0);
}

export function totals() {
  const subtotal = round(state.items.reduce((s, i) => s + i.price * i.qty, 0));
  const discount = state.promo === CONFIG.promoCode
    ? round(subtotal * (CONFIG.promoPercent / 100))
    : 0;
  const afterDiscount = round(subtotal - discount);

  // Threshold is evaluated on the post-discount figure so the promo can't be
  // used to jump the free-shipping line. Mirror any change in
  // backend/app/services.py :: price_cart().
  const shipping = state.items.length === 0
    ? 0
    : afterDiscount >= CONFIG.freeShippingThreshold ? 0 : CONFIG.flatShipping;

  return {
    subtotal,
    discount,
    shipping,
    total: round(afterDiscount + shipping),
    remainingForFreeShipping: Math.max(0, round(CONFIG.freeShippingThreshold - afterDiscount)),
  };
}

function round(n) {
  return Math.round((n + Number.EPSILON) * 100) / 100;
}

export function money(n) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n);
}

/* ---------- RUO acknowledgment ------------------------------------------- */
/* Stored with an explicit expiry so consent is re-confirmed periodically
   rather than once forever. The server keeps the authoritative audit record;
   this is only what suppresses the overlay. */

export function hasAck() {
  try {
    const raw = localStorage.getItem(ACK_KEY);
    if (!raw) return false;
    const { at } = JSON.parse(raw);
    return Date.now() - at < ACK_DAYS * 864e5;
  } catch {
    return false;
  }
}

export function setAck() {
  try {
    localStorage.setItem(ACK_KEY, JSON.stringify({ at: Date.now(), v: 1 }));
  } catch { /* overlay will reappear next visit; acceptable */ }
}
