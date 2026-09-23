/* ==========================================================================
   fx.js — v2 visual layer. Ambient motion lives on the dark glow stages
   (particles, flowing light, levitating vials); everywhere else, feedback
   only on things you can click. Content is already in the HTML.

   The motion level is on <html data-motion> (set by motion.js):
     full  everything
     calm  the system asks for reduced motion: slower, smaller, no tilting
     off   the visitor pressed pause: everything holds still
   ========================================================================== */

const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const html = document.documentElement;
const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
const systemCalm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const mode = () => html.dataset.motion || 'full';

/* ---------- pause / play ------------------------------------------------ */

function setMode(next) {
  html.dataset.motion = next;
  try {
    if (next === 'off') localStorage.setItem('vrc.motion', 'off');
    else localStorage.removeItem('vrc.motion');
  } catch { /* private mode: the choice lasts for this page only */ }
  $$('.fx-pause').forEach(syncPause);
  window.dispatchEvent(new CustomEvent('vrc:motion'));
}

function syncPause(btn) {
  const off = mode() === 'off';
  btn.setAttribute('aria-pressed', String(off));
  btn.setAttribute('aria-label', off ? 'Play background animations' : 'Pause background animations');
  btn.title = off ? 'Play animations' : 'Pause animations';
}

function addPause(stage) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'fx-pause';
  btn.innerHTML =
    '<svg class="i-pause" viewBox="0 0 14 14" aria-hidden="true"><rect x="2.5" y="2" width="3" height="10" rx="1" fill="currentColor"/><rect x="8.5" y="2" width="3" height="10" rx="1" fill="currentColor"/></svg>' +
    '<svg class="i-play" viewBox="0 0 14 14" aria-hidden="true"><path d="M3.5 2.2v9.6a.8.8 0 0 0 1.2.7l7.6-4.8a.8.8 0 0 0 0-1.4L4.7 1.5a.8.8 0 0 0-1.2.7z" fill="currentColor"/></svg>';
  btn.addEventListener('click', () => setMode(mode() === 'off' ? (systemCalm ? 'calm' : 'full') : 'off'));
  syncPause(btn);
  stage.appendChild(btn);
}

/* ---------- scroll progress + back to top -------------------------------- */

function initProgress() {
  const bar = document.createElement('div');
  bar.className = 'fx-progress';
  bar.setAttribute('aria-hidden', 'true');
  document.body.appendChild(bar);

  const top = document.createElement('button');
  top.type = 'button';
  top.className = 'fx-top';
  top.setAttribute('aria-label', 'Back to top');
  top.innerHTML =
    '<svg class="ring" viewBox="0 0 50 50" aria-hidden="true"><circle cx="25" cy="25" r="23"/></svg>' +
    '<svg class="arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5M6 11l6-6 6 6"/></svg>';
  top.addEventListener('click', () => window.scrollTo({ top: 0, behavior: mode() === 'full' ? 'smooth' : 'auto' }));
  document.body.appendChild(top);

  let ticking = false;
  const update = () => {
    const max = document.documentElement.scrollHeight - innerHeight;
    const p = max > 0 ? Math.min(1, scrollY / max) : 0;
    bar.style.setProperty('--p', p.toFixed(4));
    top.style.setProperty('--p', p.toFixed(4));
    top.classList.toggle('is-on', scrollY > 600);
    ticking = false;
  };
  addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
  update();
}

/* ---------- scroll reveals (staggered) ----------------------------------- */

const REVEAL = [
  '.sec-head', '.why-copy', '.notice-card', '.qa', '.feature', '.photo-card',
  '.num-card', '.info-card', '.dont-card', '.principle', '.faq-item', '.faq-group > h2',
  '.numbered', '.coa-table-wrap', '.doc', '.reach > *', '.commit-list li',
  '.pdp-details > *', '.split > *', '.sec .pgrid:not(#catalog) .pcard',
  '.cta-verify .inner-narrow > *', '.footer-grid > *',
];

function initReveal() {
  const els = [...new Set($$(REVEAL.join(',')))].filter((el) => !el.closest('.drawer, .gate, .fx-glow'));
  if (!('IntersectionObserver' in window) || !els.length) return;

  // Stagger siblings that share a parent.
  const counts = new Map();
  els.forEach((el) => {
    const n = counts.get(el.parentElement) || 0;
    counts.set(el.parentElement, n + 1);
    el.style.setProperty('--d', String(Math.min(n, 6)));
    if (!el.hasAttribute('data-reveal')) el.setAttribute('data-reveal', '');
  });

  // A fast scroll or a jump to an anchor can carry elements past the
  // viewport between two frames, so the observer never sees them. Whenever
  // anything reveals (and when scrolling settles), reveal everything that is
  // already at or above the viewport too, so nothing is left hidden.
  const reveal = (el) => { el.classList.add('is-in'); io.unobserve(el); };
  const revealPassed = () => {
    $$('[data-reveal]:not(.is-in), .rule:not(.is-in)').forEach((el) => {
      if (el.getBoundingClientRect().top < innerHeight) reveal(el);
    });
  };
  const io = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) revealPassed();
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
  let settle;
  addEventListener('scroll', () => { clearTimeout(settle); settle = setTimeout(revealPassed, 120); }, { passive: true });

  els.forEach((el) => io.observe(el));
  $$('.rule').forEach((el) => io.observe(el));
  html.classList.add('fx-ready');

  // Belt and braces: nothing stays hidden if an observer never fires
  // (print, odd embeds, very fast jumps to an anchor).
  addEventListener('beforeprint', () => $$('[data-reveal], .rule').forEach((el) => el.classList.add('is-in')));
  setTimeout(revealPassed, 1800);
}

/* ---------- headline: word-by-word entrance ------------------------------ */

function splitWords(el) {
  if (!el || el.dataset.split) return;
  el.dataset.split = '1';
  el.setAttribute('aria-label', el.textContent.trim().replace(/\s+/g, ' '));
  let i = 0;
  const wrap = (text) => text.split(/(\s+)/).map((part) => {
    if (!part.trim()) return document.createTextNode(part);
    const w = document.createElement('span');
    w.className = 'fx-word';
    w.setAttribute('aria-hidden', 'true');
    w.style.setProperty('--i', String(i++));
    w.textContent = part;
    return w;
  });
  [...el.childNodes].forEach((node) => {
    if (node.nodeType === 3) node.replaceWith(...wrap(node.textContent));
    else if (node.nodeType === 1) [...node.childNodes].forEach((c) => c.nodeType === 3 && c.replaceWith(...wrap(c.textContent)));
  });
}

/* ---------- home hero: the numbers count up once ------------------------ */

function initCountUp() {
  if (mode() === 'off') return;
  $$('.hero-facts strong').forEach((el) => {
    const target = Number(el.textContent);
    if (!Number.isInteger(target) || target < 2) return;
    const t0 = performance.now() + 350;
    const tick = (now) => {
      const k = Math.min(1, Math.max(0, (now - t0) / 1200));
      el.textContent = String(Math.round(target * (1 - (1 - k) ** 3)));
      if (k < 1) requestAnimationFrame(tick);
    };
    el.textContent = '0';
    requestAnimationFrame(tick);
  });
}

/* ---------- glow stages: flowing aurora + particle field ----------------
   Every .fx-glow section (home hero, page headers, product photo stage)
   gets the drifting lights, a particle canvas and a pause button. Markup
   may already carry the lights and canvas (the home hero does). Particles
   sit at different depths: near ones are bigger, faster and shift more
   when the pointer moves, which reads as 3D. */

function initGlow(stage) {
  if (!stage.querySelector(':scope > .aurora')) {
    const a = document.createElement('div');
    a.className = 'aurora'; a.setAttribute('aria-hidden', 'true');
    a.innerHTML = '<span></span><span></span><span></span>';
    stage.prepend(a);
  }
  let canvas = stage.querySelector(':scope > .hero-particles');
  if (!canvas) {
    canvas = document.createElement('canvas');
    canvas.className = 'hero-particles'; canvas.setAttribute('aria-hidden', 'true');
    stage.querySelector(':scope > .aurora').after(canvas);
  }
  addPause(stage);
  if (!canvas.getContext) return;
  const ctx = canvas.getContext('2d');
  const dpr = Math.min(devicePixelRatio || 1, 2);
  const COLORS = ['143,217,174', '172,201,193', '226,184,145', '91,192,138'];
  let w = 0, h = 0, parts = [], raf = 0, running = false, visible = false;
  const mouse = { x: -9999, y: -9999 };
  const shift = { x: 0, y: 0, tx: 0, ty: 0 };   // pointer parallax, eased

  const sprite = {};
  COLORS.forEach((c) => {           // pre-rendered glow dots: cheap to draw
    const s = document.createElement('canvas'); s.width = s.height = 32;
    const g = s.getContext('2d'); const grd = g.createRadialGradient(16, 16, 0, 16, 16, 16);
    grd.addColorStop(0, `rgba(${c},1)`); grd.addColorStop(0.25, `rgba(${c},.55)`); grd.addColorStop(1, `rgba(${c},0)`);
    g.fillStyle = grd; g.fillRect(0, 0, 32, 32); sprite[c] = s;
  });

  const spawn = (anywhere) => {
    const z = 0.35 + Math.random() * 0.65;
    return {
      x: Math.random() * w, y: anywhere ? Math.random() * h : h + 20, z,
      r: (3 + Math.random() * 8) * (0.5 + z * 0.7), vy: -(0.12 + Math.random() * 0.4) * (0.4 + z), vx: 0,
      sway: Math.random() * Math.PI * 2, c: COLORS[Math.floor(Math.random() * COLORS.length)],
      tw: Math.random() * Math.PI * 2, sx: 0, sy: 0,
    };
  };

  const resize = () => {
    const r = stage.getBoundingClientRect();
    w = r.width; h = r.height;
    canvas.width = w * dpr; canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    parts = Array.from({ length: Math.round(Math.min(110, (w * h) / 11000)) }, () => spawn(true));
    if (!running) draw(0);
  };

  // speed 0 draws a still frame (paused), 0.4 is calm, 1 is full motion.
  const draw = (speed) => {
    ctx.clearRect(0, 0, w, h);
    ctx.globalCompositeOperation = 'lighter';
    shift.x += (shift.tx - shift.x) * 0.06; shift.y += (shift.ty - shift.y) * 0.06;
    for (const p of parts) {
      p.sway += 0.01 * speed; p.tw += 0.03 * speed;
      p.x += (Math.sin(p.sway) * 0.25 + p.vx) * speed; p.y += p.vy * speed; p.vx *= 0.94;
      p.sx = p.x + shift.x * p.z; p.sy = p.y + shift.y * p.z;
      const dx = p.sx - mouse.x, dy = p.sy - mouse.y, d2 = dx * dx + dy * dy;
      if (speed && d2 < 14000) { const f = (1 - d2 / 14000) * 0.9 * p.z, d = Math.sqrt(d2 + 1); p.vx += (dx / d) * f; p.y += (dy / d) * f; }
      if (p.y < -20 || p.x < -40 || p.x > w + 40) Object.assign(p, spawn(false));
      ctx.globalAlpha = (0.25 + 0.3 * p.z) + 0.3 * Math.sin(p.tw);
      ctx.drawImage(sprite[p.c], p.sx - p.r, p.sy - p.r, p.r * 2, p.r * 2);
    }
    // faint links between close particles: a "molecular" mesh
    ctx.globalCompositeOperation = 'source-over'; ctx.lineWidth = 0.6; ctx.strokeStyle = 'rgb(172,201,193)';
    for (let i = 0; i < parts.length; i++) for (let j = i + 1; j < parts.length; j++) {
      const a = parts[i], b = parts[j], dx = a.sx - b.sx, dy = a.sy - b.sy, d2 = dx * dx + dy * dy;
      if (d2 < 9000) { ctx.globalAlpha = (1 - d2 / 9000) * 0.18 * Math.min(a.z, b.z) * 1.4;
        ctx.beginPath(); ctx.moveTo(a.sx, a.sy); ctx.lineTo(b.sx, b.sy); ctx.stroke(); }
    }
    ctx.globalAlpha = 1;
  };

  const frame = () => { draw(mode() === 'calm' ? 0.4 : 1); raf = requestAnimationFrame(frame); };
  const start = () => {
    if (!running && visible && !document.hidden && mode() !== 'off') { running = true; raf = requestAnimationFrame(frame); }
  };
  const stop = () => { running = false; cancelAnimationFrame(raf); };

  resize();
  addEventListener('resize', () => { clearTimeout(resize.t); resize.t = setTimeout(resize, 150); });
  stage.addEventListener('pointermove', (e) => {
    const r = stage.getBoundingClientRect();
    mouse.x = e.clientX - r.left; mouse.y = e.clientY - r.top;
    if (mode() === 'full' && e.pointerType === 'mouse') {
      shift.tx = (0.5 - mouse.x / r.width) * 46; shift.ty = (0.5 - mouse.y / r.height) * 30;
    }
  });
  stage.addEventListener('pointerleave', () => { mouse.x = mouse.y = -9999; shift.tx = shift.ty = 0; });
  // Only animate while the stage is on screen and the tab is visible.
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; visible ? start() : stop(); }).observe(stage);
  document.addEventListener('visibilitychange', () => (document.hidden ? stop() : start()));
  addEventListener('vrc:motion', () => { if (mode() === 'off') { stop(); draw(0); } else start(); });
}

/* ---------- hero: the vial turns toward the pointer (it is a link) ------ */

function initVial() {
  const stage = document.querySelector('.hero-stage');
  const link = stage?.querySelector('.vial-link');
  if (!link || !finePointer) return;
  stage.addEventListener('pointermove', (e) => {
    if (mode() !== 'full') return;
    const r = stage.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    link.classList.add('is-tilting');
    link.style.setProperty('--ry', `${(x * 22).toFixed(1)}deg`);
    link.style.setProperty('--rx', `${(-y * 12).toFixed(1)}deg`);
  });
  stage.addEventListener('pointerleave', () => {
    link.classList.remove('is-tilting');
    link.style.setProperty('--ry', '0deg'); link.style.setProperty('--rx', '0deg');
  });
}

/* ---------- product cards: tilt, glare and a lit edge follow the mouse -- */

function initTilt() {
  if (!finePointer) return;
  let card = null, rect = null, frame = 0, last = null;
  const reset = () => {
    if (!card) return;
    card.classList.remove('is-tilting');
    card.style.setProperty('--rx', '0deg'); card.style.setProperty('--ry', '0deg');
    card = rect = null;
  };
  const paint = () => {
    frame = 0;
    if (!card || !last) return;
    rect ||= card.getBoundingClientRect();   // measured before tilting, so it stays steady
    const x = Math.min(1, Math.max(0, (last.clientX - rect.left) / rect.width));
    const y = Math.min(1, Math.max(0, (last.clientY - rect.top) / rect.height));
    card.classList.add('is-tilting');
    card.style.setProperty('--ry', `${((x - 0.5) * 9).toFixed(2)}deg`);
    card.style.setProperty('--rx', `${((0.5 - y) * 7).toFixed(2)}deg`);
    card.style.setProperty('--mx', `${(x * 100).toFixed(1)}%`);
    card.style.setProperty('--my', `${(y * 100).toFixed(1)}%`);
  };
  document.addEventListener('pointermove', (e) => {
    if (e.pointerType !== 'mouse' || mode() !== 'full') { reset(); return; }
    const hit = e.target.closest?.('.pcard');
    if (hit !== card) { reset(); card = hit; }
    if (!card) return;
    last = e;
    if (!frame) frame = requestAnimationFrame(paint);
  }, { passive: true });
  document.addEventListener('pointerout', (e) => { if (card && !card.contains(e.relatedTarget)) reset(); });
  addEventListener('scroll', () => { rect = null; }, { passive: true });
}

/* ---------- large buttons lean toward the cursor ------------------------ */

function initMagnet() {
  if (!finePointer) return;
  document.addEventListener('pointermove', (e) => {
    const btn = e.target.closest?.('.btn-lg');
    if (!btn || e.pointerType !== 'mouse' || mode() !== 'full') return;
    const r = btn.getBoundingClientRect();
    const dx = (e.clientX - (r.left + r.width / 2)) * 0.22;
    const dy = (e.clientY - (r.top + r.height / 2)) * 0.3;
    btn.classList.add('is-magnet');
    btn.style.translate = `${Math.max(-8, Math.min(8, dx)).toFixed(1)}px ${Math.max(-6, Math.min(6, dy)).toFixed(1)}px`;
  }, { passive: true });
  document.addEventListener('pointerout', (e) => {
    const btn = e.target.closest?.('.btn-lg');
    if (btn && !btn.contains(e.relatedTarget)) { btn.classList.remove('is-magnet'); btn.style.translate = ''; }
  });
}

/* ---------- buttons: ripple on press ----------------------------------- */

function initButtons() {
  document.addEventListener('pointerdown', (e) => {
    const btn = e.target.closest('.btn, .chip');
    if (!btn || btn.disabled || mode() === 'off') return;
    const r = btn.getBoundingClientRect();
    const size = Math.max(r.width, r.height);
    const dot = document.createElement('span');
    dot.className = 'fx-ripple';
    dot.style.width = dot.style.height = `${size}px`;
    dot.style.left = `${e.clientX - r.left - size / 2}px`;
    dot.style.top = `${e.clientY - r.top - size / 2}px`;
    btn.appendChild(dot);
    setTimeout(() => dot.remove(), 650);
  });
}

/* ---------- add to cart: fly to the cart, burst, badge pop -------------- */

function burst(x, y) {
  const colors = ['#B8794A', '#D0A07A', '#2F8F4A', '#0F3433', '#EDE6D4'];
  for (let i = 0; i < 14; i++) {
    const s = document.createElement('span');
    s.className = 'fx-spark';
    const a = (Math.PI * 2 * i) / 14 + Math.random() * 0.4;
    const d = 26 + Math.random() * 34;
    s.style.left = `${x}px`;
    s.style.top = `${y}px`;
    s.style.background = colors[i % colors.length];
    s.style.setProperty('--dx', `${Math.cos(a) * d}px`);
    s.style.setProperty('--dy', `${Math.sin(a) * d}px`);
    document.body.appendChild(s);
    setTimeout(() => s.remove(), 750);
  }
}

function initCartFx() {
  const target = () => document.querySelector('.header-tools [data-cart-open]');

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-add]');
    if (!btn) return;

    const label = btn.textContent;
    btn.classList.add('fx-added');
    btn.textContent = 'Added ✓';
    setTimeout(() => { btn.classList.remove('fx-added'); btn.textContent = label; }, 1300);
    if (mode() === 'off') return;

    setTimeout(() => {
      document.querySelectorAll('[data-cart-count]').forEach((c) => {
        c.classList.remove('fx-pop'); void c.offsetWidth; c.classList.add('fx-pop');
      });
    }, mode() === 'full' ? 650 : 0);
    if (mode() !== 'full') return;

    const r = btn.getBoundingClientRect();
    burst(r.left + r.width / 2, r.top + r.height / 2);

    const img = btn.closest('.pcard, .pdp')?.querySelector('.pcard-media img, .pdp-media img');
    const cart = target();
    if (img && cart && img.animate) {
      const from = img.getBoundingClientRect();
      const to = cart.getBoundingClientRect();
      const fly = document.createElement('div');
      fly.className = 'fx-fly';
      fly.innerHTML = `<img src="${img.currentSrc || img.src}" alt="">`;
      fly.style.left = `${from.left + from.width / 2 - 32}px`;
      fly.style.top = `${from.top + from.height / 2 - 40}px`;
      document.body.appendChild(fly);
      const dx = to.left + to.width / 2 - (from.left + from.width / 2);
      const dy = to.top + to.height / 2 - (from.top + from.height / 2);
      fly.animate([
        { transform: 'translate(0,0) scale(1.2) rotate(0)', opacity: 1 },
        { transform: `translate(${dx * 0.55}px, ${dy * 0.55 - 80}px) scale(.8) rotate(-12deg)`, opacity: 1, offset: 0.6 },
        { transform: `translate(${dx}px, ${dy}px) scale(.2) rotate(-20deg)`, opacity: 0.2 },
      ], { duration: 750, easing: 'cubic-bezier(.5,0,.3,1)' }).onfinish = () => fly.remove();
    }
  });
}

/* ---------- shop: cards settle in as search results change --------------
   Category and sort changes glide the cards to their new places (a view
   transition, in ui.js). Typing in search can't use that, since a view
   transition freezes the page, including the text box, while it runs. */

function initShopFx() {
  const grid = document.getElementById('catalog');
  if (!grid) return;
  const replay = () => setTimeout(() => {
    if (mode() !== 'full') return;
    $$('.pcard:not([hidden])', grid).forEach((card, i) => {
      card.classList.remove('fx-enter');
      card.style.setProperty('--i', String(Math.min(i, 12)));
      void card.offsetWidth;
      card.classList.add('fx-enter');
    });
  }, 140);
  document.getElementById('catalog-search')?.addEventListener('input', replay);
  if (!document.startViewTransition) {
    $$('.chip').forEach((c) => c.addEventListener('click', replay));
    document.getElementById('catalog-sort')?.addEventListener('change', replay);
  }
}

export function initFx() {
  initProgress();
  splitWords(document.querySelector('.hero-copy h1'));
  splitWords(document.querySelector('.page-hero h1'));
  initReveal();
  initCountUp();
  $$('.fx-glow').forEach(initGlow);
  initVial();
  initTilt();
  initMagnet();
  initButtons();
  initCartFx();
  initShopFx();
}
