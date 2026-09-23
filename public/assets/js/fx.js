/* ==========================================================================
   fx.js — motion layer. Pure decoration on top of ui.js: every effect is
   optional, content is already in the HTML, and nothing runs for visitors
   who ask for reduced motion.
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
  '.pdp-details > *', '.split > *', '.bestsellers-grid .pcard', '.sec .pgrid:not(#catalog) .pcard',
  '.cta-verify .inner-narrow > *', '.footer-grid > *',
];

function initReveal() {
  const els = [...new Set($$(REVEAL.join(',')))].filter((el) => !el.closest('.drawer, .gate'));
  if (!('IntersectionObserver' in window) || !els.length) return;

  // Stagger siblings that share a parent.
  const counts = new Map();
  els.forEach((el) => {
    const n = counts.get(el.parentElement) || 0;
    counts.set(el.parentElement, n + 1);
    el.style.setProperty('--d', String(Math.min(n, 6)));
    if (!el.hasAttribute('data-reveal')) el.setAttribute('data-reveal', '');
  });
  $$('.why-copy').forEach((el) => el.setAttribute('data-reveal', 'left'));
  $$('.photo-cards .photo-card').forEach((el) => el.setAttribute('data-reveal', 'right'));

  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-in');
      io.unobserve(entry.target);
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });

  els.forEach((el) => io.observe(el));
  $$('.rule').forEach((el) => io.observe(el));
  document.documentElement.classList.add('fx-ready');

  // Belt and braces: nothing stays hidden if an observer never fires
  // (print, odd embeds, very fast jumps to an anchor).
  addEventListener('beforeprint', () => $$('[data-reveal], .rule').forEach((el) => el.classList.add('is-in')));
  setTimeout(() => {
    $$('[data-reveal]:not(.is-in)').forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.top < innerHeight && r.bottom > 0) el.classList.add('is-in');
    });
  }, 1800);
}

/* ---------- headline: word-by-word entrance ------------------------------ */

function splitWords(el) {
  if (!el || el.dataset.split) return;
  const words = el.textContent.trim().split(/\s+/);
  el.dataset.split = '1';
  el.setAttribute('aria-label', el.textContent.trim());
  el.innerHTML = words
    .map((w, i) => `<span class="fx-word" aria-hidden="true" style="--i:${i}">${w.replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`)}</span>`)
    .join(' ');
}

/* ---------- hero: cursor glow + parallax vial --------------------------- */

function initHero() {
  const hero = document.querySelector('.hero');
  if (!hero || !finePointer) return;
  const photo = hero.querySelector('.hero-photo');
  hero.addEventListener('pointermove', (e) => {
    const r = hero.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width;
    const y = (e.clientY - r.top) / r.height;
    hero.style.setProperty('--mx', `${(x * 100).toFixed(1)}%`);
    hero.style.setProperty('--my', `${(y * 100).toFixed(1)}%`);
    if (photo) {
      photo.style.setProperty('--px', `${((x - 0.5) * -18).toFixed(1)}px`);
      photo.style.setProperty('--py', `${((y - 0.5) * -14).toFixed(1)}px`);
    }
  });
  hero.addEventListener('pointerleave', () => {
    photo?.style.setProperty('--px', '0px');
    photo?.style.setProperty('--py', '0px');
  });
}

/* ---------- cards: 3D tilt + spotlight ----------------------------------- */

function initTilt() {
  if (!finePointer) return;
  const cards = $$('.pcard, .photo-card, .num-card, .info-card, .dont-card');
  cards.forEach((card) => {
    card.setAttribute('data-tilt', '');
    card.classList.add('fx-spot');
    const max = card.classList.contains('photo-card') ? 6 : 5;
    card.addEventListener('pointermove', (e) => {
      const r = card.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width;
      const y = (e.clientY - r.top) / r.height;
      card.classList.add('is-tilting');
      card.style.transform =
        `perspective(900px) rotateX(${((0.5 - y) * max).toFixed(2)}deg) rotateY(${((x - 0.5) * max).toFixed(2)}deg) translateY(-4px)`;
      card.style.setProperty('--sx', `${(x * 100).toFixed(1)}%`);
      card.style.setProperty('--sy', `${(y * 100).toFixed(1)}%`);
    });
    card.addEventListener('pointerleave', () => {
      card.classList.remove('is-tilting');
      card.style.transform = '';
    });
  });
}

/* ---------- buttons: magnetic pull + ripple ----------------------------- */

function initButtons() {
  if (finePointer) {
    $$('.btn-lg, .tool-btn, .gate-actions .btn').forEach((btn) => {
      btn.addEventListener('pointermove', (e) => {
        const r = btn.getBoundingClientRect();
        const dx = e.clientX - (r.left + r.width / 2);
        const dy = e.clientY - (r.top + r.height / 2);
        btn.style.transform = `translate(${(dx * 0.18).toFixed(1)}px, ${(dy * 0.28).toFixed(1)}px)`;
      });
      btn.addEventListener('pointerleave', () => { btn.style.transform = ''; });
    });
  }

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

/* ---------- animated borders ------------------------------------------- */

function initBorders() {
  $$('.notice-card, .coa-card, .gate-card').forEach((el) => el.classList.add('fx-border'));
}

export function initFx() {
  if (reduced) return;
  initProgress();
  splitWords(document.querySelector('.hero-copy h1'));
  splitWords(document.querySelector('.page-hero h1'));
  initReveal();
  initHero();
  initTilt();
  initButtons();
  initCartFx();
  initShopFx();
  initBorders();
}
