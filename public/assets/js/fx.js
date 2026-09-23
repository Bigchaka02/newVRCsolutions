/* ==========================================================================
   fx.js — v2 visual layer. Ambient motion only in the home hero
   (particles, levitating vial); elsewhere, feedback only on things you
   can click. Content is already in the HTML; reduced motion turns it off.
   ========================================================================== */

const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

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
  top.addEventListener('click', () => window.scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' }));
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
  document.documentElement.classList.add('fx-ready');

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

/* ---------- glow stages: flowing aurora + particle field ----------------
   Every .fx-glow section (home hero, page headers, product photo stage)
   gets the drifting lights and a particle canvas. Markup may already carry
   them (the home hero does); otherwise they are added here. */

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
  if (!canvas.getContext) return;
  const ctx = canvas.getContext('2d');
  const dpr = Math.min(devicePixelRatio || 1, 2);
  const COLORS = ['143,217,174', '172,201,193', '226,184,145', '91,192,138'];
  let w = 0, h = 0, parts = [], raf = 0, running = false;
  const mouse = { x: -9999, y: -9999 };

  const sprite = {};
  COLORS.forEach((c) => {           // pre-rendered glow dots: cheap to draw
    const s = document.createElement('canvas'); s.width = s.height = 32;
    const g = s.getContext('2d'); const grd = g.createRadialGradient(16, 16, 0, 16, 16, 16);
    grd.addColorStop(0, `rgba(${c},1)`); grd.addColorStop(0.25, `rgba(${c},.55)`); grd.addColorStop(1, `rgba(${c},0)`);
    g.fillStyle = grd; g.fillRect(0, 0, 32, 32); sprite[c] = s;
  });

  const spawn = (anywhere) => ({
    x: Math.random() * w, y: anywhere ? Math.random() * h : h + 20,
    r: 3 + Math.random() * 9, vy: -(0.15 + Math.random() * 0.45), vx: 0,
    sway: Math.random() * Math.PI * 2, c: COLORS[Math.floor(Math.random() * COLORS.length)],
    tw: Math.random() * Math.PI * 2,
  });

  const resize = () => {
    const r = stage.getBoundingClientRect();
    w = r.width; h = r.height;
    canvas.width = w * dpr; canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    parts = Array.from({ length: Math.round(Math.min(110, (w * h) / 11000)) }, () => spawn(true));
  };

  const frame = () => {
    ctx.clearRect(0, 0, w, h);
    ctx.globalCompositeOperation = 'lighter';
    for (const p of parts) {
      p.sway += 0.01; p.tw += 0.03;
      p.x += Math.sin(p.sway) * 0.25 + p.vx; p.y += p.vy; p.vx *= 0.94;
      const dx = p.x - mouse.x, dy = p.y - mouse.y, d2 = dx * dx + dy * dy;
      if (d2 < 14000) { const f = (1 - d2 / 14000) * 0.9, d = Math.sqrt(d2 + 1); p.vx += (dx / d) * f; p.y += (dy / d) * f; }
      if (p.y < -20 || p.x < -30 || p.x > w + 30) Object.assign(p, spawn(false));
      ctx.globalAlpha = 0.35 + 0.35 * Math.sin(p.tw);
      ctx.drawImage(sprite[p.c], p.x - p.r, p.y - p.r, p.r * 2, p.r * 2);
    }
    // faint links between close particles: a "molecular" mesh
    ctx.globalCompositeOperation = 'source-over'; ctx.lineWidth = 0.6; ctx.strokeStyle = 'rgb(172,201,193)';
    for (let i = 0; i < parts.length; i++) for (let j = i + 1; j < parts.length; j++) {
      const a = parts[i], b = parts[j], dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy;
      if (d2 < 9000) { ctx.globalAlpha = (1 - d2 / 9000) * 0.18;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); }
    }
    ctx.globalAlpha = 1;
    raf = requestAnimationFrame(frame);
  };
  let visible = false;
  const start = () => { if (!running && visible && !document.hidden) { running = true; raf = requestAnimationFrame(frame); } };
  const stop = () => { running = false; cancelAnimationFrame(raf); };

  resize();
  addEventListener('resize', () => { clearTimeout(resize.t); resize.t = setTimeout(resize, 150); });
  stage.addEventListener('pointermove', (e) => { const r = stage.getBoundingClientRect(); mouse.x = e.clientX - r.left; mouse.y = e.clientY - r.top; });
  stage.addEventListener('pointerleave', () => { mouse.x = mouse.y = -9999; });
  // Only animate while the stage is on screen and the tab is visible.
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; visible ? start() : stop(); }).observe(stage);
  document.addEventListener('visibilitychange', () => (document.hidden ? stop() : start()));
}

/* ---------- hero: the vial turns toward the pointer (it is a link) ------ */

function initVial() {
  const stage = document.querySelector('.hero-stage');
  const link = stage?.querySelector('.vial-link');
  if (!link || !finePointer) return;
  stage.addEventListener('pointermove', (e) => {
    const r = stage.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    link.style.setProperty('--ry', `${(x * 22).toFixed(1)}deg`);
    link.style.setProperty('--rx', `${(-y * 12).toFixed(1)}deg`);
  });
  stage.addEventListener('pointerleave', () => { link.style.setProperty('--ry', '0deg'); link.style.setProperty('--rx', '0deg'); });
}

/* ---------- buttons: ripple on press ----------------------------------- */

function initButtons() {
  document.addEventListener('pointerdown', (e) => {
    const btn = e.target.closest('.btn, .chip');
    if (!btn || btn.disabled) return;
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

    const r = btn.getBoundingClientRect();
    burst(r.left + r.width / 2, r.top + r.height / 2);

    const label = btn.textContent;
    btn.classList.add('fx-added');
    btn.textContent = 'Added ✓';
    setTimeout(() => { btn.classList.remove('fx-added'); btn.textContent = label; }, 1300);

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

    setTimeout(() => {
      document.querySelectorAll('[data-cart-count]').forEach((c) => {
        c.classList.remove('fx-pop'); void c.offsetWidth; c.classList.add('fx-pop');
      });
    }, 650);
  });
}

/* ---------- shop: re-animate cards when filters change ------------------ */

function initShopFx() {
  const grid = document.getElementById('catalog');
  if (!grid) return;
  const replay = () => setTimeout(() => {
    $$('.pcard:not([hidden])', grid).forEach((card, i) => {
      card.classList.remove('fx-enter');
      card.style.setProperty('--i', String(Math.min(i, 12)));
      void card.offsetWidth;
      card.classList.add('fx-enter');
    });
  }, 140);
  $$('.chip').forEach((c) => c.addEventListener('click', replay));
  document.getElementById('catalog-sort')?.addEventListener('change', replay);
  document.getElementById('catalog-search')?.addEventListener('input', replay);
}

export function initFx() {
  if (reduced) return;
  initProgress();
  splitWords(document.querySelector('.hero-copy h1'));
  splitWords(document.querySelector('.page-hero h1'));
  initReveal();
  $$('.fx-glow').forEach(initGlow);
  initVial();
  initButtons();
  initCartFx();
  initShopFx();
}
