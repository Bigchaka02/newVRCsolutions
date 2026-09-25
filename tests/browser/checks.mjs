// Customer-journey and layout checks against the built site. Prints PASS/FAIL
// per check and exits non-zero on any failure. See HANDOFF.md > Testing.
//
//   BASE=http://localhost:8080 node tests/browser/checks.mjs
//
// Works with or without the API behind BASE: checkout either places the order
// or shows the "isn't connected to its server yet" message.
import { chromium } from 'playwright';

const B = (process.env.BASE || 'http://localhost:8080').replace(/\/$/, '');
const b = await chromium.launch();
const out = [], errors = [];
let failed = 0;
const ok = (name, cond, info = '') => { if (!cond) failed++; out.push(`${cond ? 'PASS' : 'FAIL'}  ${name}${info ? '  (' + info + ')' : ''}`); };
const page = async (opts = {}, ack = true) => {
  const c = await b.newContext({ viewport: { width: 1440, height: 900 }, ...opts });
  if (ack) await c.addInitScript(() => localStorage.setItem('vrc.ruo-ack.v1', JSON.stringify({ at: Date.now(), v: 1 })));
  const p = await c.newPage();
  p.on('pageerror', (e) => errors.push(`${p.url()} ${e.message}`));
  p.on('console', (m) => m.type() === 'error' && !/Failed to load resource/.test(m.text()) && errors.push(`${p.url()} ${m.text()}`));
  return p;
};
const gapBelowHeader = (p, sel) => p.evaluate((sel) => Math.round(
  document.querySelector(sel).getBoundingClientRect().top - document.querySelector('.site-header').getBoundingClientRect().bottom), sel);
const moving = (p, sel) => p.evaluate((sel) => new Promise((res) => {
  const cv = document.querySelector(sel); if (!cv || !cv.width) return res(false);
  const a = cv.toDataURL(); setTimeout(() => res(a !== cv.toDataURL()), 600);
}), sel);

// Research-use gate on first visit, above the sticky discount bar
{
  const p = await page({}, false);
  await p.goto(B + '/', { waitUntil: 'networkidle' });
  ok('RUO gate opens on first visit', (await p.getAttribute('#ruo-gate', 'data-open')) === 'true');
  const top = await p.evaluate(() => document.elementFromPoint(720, 10).closest('.gate, .topbar')?.className);
  ok('gate covers the discount bar', /gate/.test(top || ''), top);
  ok('enter button disabled until both boxes are ticked', await p.isDisabled('#gate-enter'));
  await p.check('#ruo-gate .check:nth-child(1) input'); await p.check('#ruo-gate .check:nth-child(2) input');
  await p.click('#gate-enter');
  ok('gate closes after confirming', (await p.getAttribute('#ruo-gate', 'data-open')) !== 'true');
  await p.context().close();
}

// Animations run, including for visitors whose system asks for reduced motion
for (const reducedMotion of ['no-preference', 'reduce']) {
  const p = await page({ reducedMotion });
  await p.goto(B + '/', { waitUntil: 'networkidle' });
  const mode = await p.evaluate(() => document.documentElement.dataset.motion);
  ok(`hero particles move (${reducedMotion} -> ${mode})`, await moving(p, '.hero-particles'));
  await p.context().close();
}

// Shop: filters, sort, search, cart, promo
{
  const p = await page();
  await p.goto(B + '/shop/', { waitUntil: 'networkidle' });
  ok('shop lists 23 products', (await p.locator('#catalog .pcard').count()) === 23);
  // Filtering runs inside a view transition, so the grid updates a beat after the click.
  const shown = (n) => p.waitForFunction((n) => document.querySelectorAll('#catalog .pcard:not([hidden])').length === n, n, { timeout: 5000 }).then(() => true, () => false);
  await p.click('.chip[data-filter="solvents"]');
  ok('Solvents filter shows 3', await shown(3));
  await p.click('.chip[data-filter="all"]');
  ok('All shows 23 again', await shown(23));
  await p.selectOption('#catalog-sort', 'price-asc'); await p.waitForTimeout(800);
  const first = await p.textContent('#catalog .pcard:not([hidden]) .pcard-price');
  ok('price sort puts the cheapest first', first.trim() === '$7.99', first.trim());
  await p.locator('#catalog [data-add]').first().click(); await p.waitForTimeout(700);
  ok('add to cart opens the drawer', (await p.getAttribute('#cart-drawer', 'data-open')) === 'true');
  const top = await p.evaluate(() => document.elementFromPoint(1300, 10).closest('.drawer, .topbar')?.className);
  ok('drawer covers the discount bar', /drawer/.test(top || ''), top);
  await p.fill('#promo-input', 'first15'); await p.click('#promo-form button'); await p.waitForTimeout(300);
  ok('promo FIRST15 applies', /FIRST15/.test(await p.textContent('#cart-totals')));
  await p.locator('.drawer .line-qty button').last().click(); await p.waitForTimeout(300);
  ok('quantity + updates the badge', (await p.textContent('.header-tools [data-cart-count]')).trim() === '2');
  await p.keyboard.press('Escape'); await p.waitForTimeout(400);
  ok('drawer closes on Escape', (await p.getAttribute('#cart-drawer', 'data-open')) === 'false');
  await p.click('[data-search-open]'); await p.fill('#site-search-q', 'bac');
  await Promise.all([p.waitForURL(/\?q=bac/), p.keyboard.press('Enter')]);
  await p.waitForLoadState('networkidle'); await p.waitForTimeout(400);
  const n = await p.locator('#catalog .pcard:not([hidden])').count();
  ok('header search filters the shop', n > 0 && n < 23, `${n} cards`);
  await p.context().close();
}

// Product page, COA library, back navigation
{
  const p = await page();
  await p.goto(B + '/shop/', { waitUntil: 'networkidle' });
  await p.locator('#catalog .pcard-title a').nth(2).click(); await p.waitForLoadState('networkidle');
  ok('card opens its product page', /\/product\//.test(p.url()));
  await p.goBack(); await p.waitForLoadState('networkidle'); await p.waitForTimeout(800);
  const named = await p.evaluate(() => [...document.querySelectorAll('*')].filter((e) => e.style?.viewTransitionName && e.style.viewTransitionName !== 'none').length);
  ok('back to shop leaves no transition names behind', named === 0, `named=${named}`);
  await p.goto(B + '/coa-library/', { waitUntil: 'networkidle' });
  await p.fill('#ledger-search', 'AS-BPC10'); await p.waitForTimeout(300);
  ok('COA library search finds a lot', /1 /.test(await p.textContent('#ledger-count')));
  await p.context().close();
}

// Sticky bar + header: anchor jumps land below them
for (const w of [1440, 390]) {
  const p = await page({ viewport: { width: w, height: 844 } });
  await p.goto(B + '/faq/#shipping', { waitUntil: 'networkidle' }); await p.waitForTimeout(800);
  const gap = await gapBelowHeader(p, '#shipping');
  ok(`FAQ anchor lands below the header at ${w}px`, gap >= 0 && gap < 60, `gap=${gap}px`);
  await p.context().close();
}

// Phone menu
{
  const p = await page({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  await p.goto(B + '/', { waitUntil: 'networkidle' });
  await p.evaluate(() => scrollTo(0, 1500)); await p.waitForTimeout(300);
  await p.click('#burger'); await p.waitForTimeout(400);
  const link = p.locator('#mobile-nav a', { hasText: 'FAQ' });
  const bx = await link.boundingBox();
  const hit = await p.evaluate(([x, y]) => document.elementFromPoint(x, y)?.textContent.trim(), [bx.x + 10, bx.y + bx.height / 2]);
  ok('phone menu links are on top and clickable', hit === 'FAQ', `hit=${hit}`);
  await p.context().close();
}

// Checkout: places the order with an API, explains itself without one
{
  const p = await page();
  await p.goto(B + '/product/bpc-157-10mg/', { waitUntil: 'networkidle' });
  await p.click('.buy-row [data-add]'); await p.waitForTimeout(400);
  await p.goto(B + '/checkout/', { waitUntil: 'networkidle' }); await p.waitForTimeout(800);
  await p.fill('input[name=email]', 'lab@example.com'); await p.fill('input[name=name]', 'A Researcher');
  await p.fill('input[name=address1]', '1 Lab St'); await p.fill('input[name=city]', 'Louisville');
  await p.fill('input[name=state]', 'KY'); await p.fill('input[name=postal_code]', '40241');
  await p.check('input[value=venmo]'); await p.check('input[name=ruo_confirmed]');
  await p.click('#checkout-form button[type=submit]'); await p.waitForTimeout(1500);
  const text = (await p.textContent('main')).replace(/\s+/g, ' ');
  ok('checkout places the order or explains the missing server',
    /VRC-[A-Z0-9]+|isn't connected to its server/.test(text));
  await p.context().close();
}

console.log(out.join('\n'));
console.log(errors.length ? 'JS ERRORS:\n' + [...new Set(errors)].join('\n') : 'no JS errors');
await b.close();
process.exit(failed || errors.length ? 1 : 0);
