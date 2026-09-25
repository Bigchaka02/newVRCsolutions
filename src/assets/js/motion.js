/* ==========================================================================
   motion.js — a classic script in <head>, so it runs before first paint.

   1. Picks the motion level and sets it on <html data-motion="…">:
        full  the default
        calm  the visitor's system asks for reduced motion. Effects stay, but
              slower and smaller, and nothing slides across the screen.
   2. Page-to-page transitions: when you open a product, its vial image
      morphs from the card you clicked into the product page, and back.
      These handlers must be registered before the new page first renders,
      which is why they live here rather than in the deferred modules.
   ========================================================================== */
(function () {
  var root = document.documentElement;
  var calm = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  root.dataset.motion = calm ? 'calm' : 'full';
  // An earlier version had a pause button that saved 'off' here; forget it.
  try { localStorage.removeItem('vrc.motion'); } catch (e) { /* private mode */ }

  var NAME = 'product-vial';
  var slug = function (url) {
    var m = /\/product\/([^/]+)\/?$/.exec(new URL(url, location.href).pathname);
    return m ? m[1] : null;
  };
  var onScreen = function (el) {
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth;
  };
  // The visible image that stands for this product on the current page:
  // a product card, the hero vial link, or the product page's own vial.
  var imageFor = function (s) {
    if (!s) return null;
    var own = slug(location.href) === s && document.querySelector('.pdp-stage img.vial');
    if (own && onScreen(own)) return own;
    var links = document.querySelectorAll('a[href$="/product/' + s + '/"]');
    for (var i = 0; i < links.length; i++) {
      var box = links[i].closest('.pcard') || links[i];
      var img = box.querySelector('.pcard-media img, img.vial');
      if (img && onScreen(img)) return img;
    }
    return null;
  };
  var tag = function (el, transition) {
    // Only one element may carry the name, and only for this transition.
    document.querySelectorAll('.pdp-stage img.vial').forEach(function (v) { v.style.viewTransitionName = 'none'; });
    el.style.viewTransitionName = NAME;
    transition.finished.finally(function () { el.style.viewTransitionName = ''; });
  };

  addEventListener('pageswap', function (e) {
    var vt = e.viewTransition;
    if (!vt || root.dataset.motion !== 'full' || !e.activation) return;
    var to = slug(e.activation.entry.url);
    var from = slug(location.href);
    var el = imageFor(to) || imageFor(from);
    if (el) tag(el, vt);
  });

  addEventListener('pagereveal', function (e) {
    var vt = e.viewTransition;
    if (!vt || root.dataset.motion !== 'full' || !window.navigation || !navigation.activation || !navigation.activation.from) return;
    var from = slug(navigation.activation.from.url);
    var here = slug(location.href);
    var el = imageFor(here) || imageFor(from);
    if (el) tag(el, vt);
  });
})();
