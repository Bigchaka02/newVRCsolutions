// Crawl every page of the built site and report broken links, broken images,
// JS errors, content left hidden by scroll reveals, and sideways scrolling at
// five screen widths. See HANDOFF.md > Testing for how to run it.
//
//   BASE=http://localhost:8080 node tests/browser/crawl.mjs
import { chromium } from 'playwright';

const BASE = (process.env.BASE || 'http://localhost:8080').replace(/\/$/, '');
const ROOT = new URL(BASE).pathname.replace(/\/$/, '');    // "" or e.g. "/newVRCsolutions"
const ORIGIN = new URL(BASE).origin;
const ack = () => localStorage.setItem('vrc.ruo-ack.v1', JSON.stringify({ at: Date.now(), v: 1 }));

const b = await chromium.launch();
const issues = [];
const seen = new Set();
const queue = [ROOT + '/'];

const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
await ctx.addInitScript(ack);
const p = await ctx.newPage();
p.on('pageerror', (e) => issues.push(`JS ${p.url()} ${e.message}`));
p.on('console', (m) => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) issues.push(`console ${p.url()} ${m.text()}`); });
p.on('response', (r) => { if (r.status() >= 400 && !r.url().includes('/api/')) issues.push(`${r.status()} ${r.url()}`); });

while (queue.length) {
  const path = queue.shift();
  if (seen.has(path)) continue;
  seen.add(path);
  const res = await p.goto(ORIGIN + path, { waitUntil: 'networkidle' });
  if (!res || res.status() !== 200) { issues.push(`page ${res && res.status()} ${path}`); continue; }
  await p.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += 600) { scrollTo(0, y); await new Promise((r) => setTimeout(r, 40)); }
    scrollTo(0, document.body.scrollHeight);
  });
  await p.waitForLoadState('networkidle'); await p.waitForTimeout(1000);
  (await p.evaluate(() => [...document.images].filter((i) => i.complete && i.naturalWidth === 0).map((i) => i.src)))
    .forEach((s) => issues.push(`broken img ${s} on ${path}`));
  // fx.js reveals an element once it is past the bottom 8% of the screen, so
  // only count elements clearly above that line.
  const hidden = await p.evaluate(() => [...document.querySelectorAll('[data-reveal]')]
    .filter((e) => !e.classList.contains('is-in') && e.getBoundingClientRect().top < innerHeight * 0.9).length);
  if (hidden) issues.push(`${hidden} elements still hidden on ${path}`);
  for (const h of await p.evaluate(() => [...document.querySelectorAll('a[href]')].map((a) => a.getAttribute('href')))) {
    if (!h.startsWith('/') || h.startsWith('//')) continue;
    if (ROOT && !h.startsWith(ROOT + '/')) { issues.push(`link missing base path ${h} on ${path}`); continue; }
    const u = h.split('#')[0].split('?')[0];
    if (!seen.has(u) && !u.startsWith(ROOT + '/api/')) queue.push(u);
  }
}

for (const w of [320, 390, 768, 1024, 1440]) {
  const c = await b.newContext({ viewport: { width: w, height: 900 } });
  await c.addInitScript(ack);
  const q = await c.newPage();
  for (const path of seen) {
    await q.goto(ORIGIN + path, { waitUntil: 'domcontentloaded' }); await q.waitForTimeout(150);
    const ov = await q.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (ov > 0) issues.push(`sideways scroll ${ov}px at ${w}px on ${path}`);
  }
  await c.close();
}

console.log(`pages crawled: ${seen.size}`);
console.log(issues.length ? [...new Set(issues)].join('\n') : 'NO ISSUES');
await b.close();
process.exit(issues.length ? 1 : 0);
