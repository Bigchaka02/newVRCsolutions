# VRC Solutions — storefront

Rebuild of [vrcsolutions.co](https://vrcsolutions.co), replacing WordPress +
WooCommerce with a pre-rendered static site and a small Python API.

> **Status: working preview with placeholders.** The site, cart, checkout and
> order lookup work end to end. Catalog data, legal copy and every external
> connection the old site had (card processor, shipping, email provider,
> analytics) are placeholders until the original backend and data are
> supplied. Nothing here should go live before the checklist at the bottom is
> done, and `python3 build.py --strict` passes.

---

## Run it locally

Needs Python 3.11+.

```bash
python3 build.py                 # generates public/ from data/ and src/
cd backend
cp .env.example .env             # then set ADMIN_TOKEN, IP_HASH_SALT, SERVE_STATIC=true
./run.sh                         # installs, seeds the database, serves on :8000
```

Open http://localhost:8000. With `SERVE_STATIC=true` one process serves the
pages and the API. API docs are at http://localhost:8000/api/docs (disabled
when `APP_ENV=production`).

## Deploy

**Fastest: one container (site + API).** Point Render, Railway or Fly.io at
this repo; they detect the `Dockerfile`. Then:

1. Add a persistent volume mounted at `/data` (the SQLite database lives
   there; without it, orders are lost on every redeploy).
2. Set environment variables: `ADMIN_TOKEN` (long random string),
   `IP_HASH_SALT` (random), `CORS_ORIGINS=https://vrcsolutions.co`, plus the
   payment handles and SMTP settings from `backend/.env.example`.
3. Point `vrcsolutions.co` at the service.

Put Cloudflare (or any proxy) in front for TLS and caching, and copy the
`Content-Security-Policy` line from `public/_headers` into it, since the
container doesn't send that header itself.

**Alternative: static site on Cloudflare Pages + API elsewhere.** Connect the
repo to Pages with build command `python3 build.py` and output directory
`public`. Pages reads `public/_headers` (security headers) and
`public/_redirects` (old WordPress URLs) automatically. Run the API from the
same Dockerfile on its own host, set `site.api_base` in
`data/products.json` to that URL, rebuild, and add the site's origin to
`CORS_ORIGINS`.

**Preview: GitHub Pages.** `.github/workflows/pages.yml` builds the site with
`python3 build.py --base-path /newVRCsolutions` and publishes it on every push
to `main` (one-time setup: Settings > Pages > Source: GitHub Actions). It
serves the static pages only, marked `noindex`; checkout, contact and order
lookup need the API from one of the options above. GitHub Pages is not meant
to run a store, so use it for previews only.

## How it's organised

```
data/products.json      Single source of truth: catalog, lots, COA links, site info
build.py                Generates public/ from data/ and src/  (--strict before launch)
src/layout.html         Shared shell: header, footer, cart drawer, RUO gate
src/product.html        Product page template (rendered once per product)
src/pages/*.html        Page bodies, with front matter (title, description, path, gate)
public/                 BUILT OUTPUT. Deploy this; don't edit it by hand
  assets/css|js|fonts   Styles, scripts, self-hosted Inter + IBM Plex Mono (OFL, licenses included)
  assets/img            Product photos, homepage photos, icons
  _headers _redirects   Security headers; 301s from retired WordPress URLs
backend/app/            FastAPI app: catalog, pricing, orders, contact, admin
backend/app/integrations/  External services, placeholders (see below)
backend/tests/          API tests:  cd backend && python -m pytest -q
Dockerfile              One-container deploy
```

`public/` is committed so the repo deploys without a build step, but it is
generated: edit `data/` and `src/`, then run `python3 build.py`.

URLs match the old site exactly (`/shop/`, `/faq/`, `/product/<slug>/`), so
search rankings carry over. Retired URLs (`/cart/`, `/my-account/`, category
pages, `/terms-of-service/`) redirect; edit `LEGACY_REDIRECTS` in `build.py`.

## Editing content

- **Publish a COA or rotate a lot:** edit the product in `data/products.json`
  (`lot`, `coa_url`, `purity`, `purity_method`, `tested`), remove the fields
  you've confirmed from its `review` list, then `python3 build.py` and
  `cd backend && python -m app.seed`.
- **Keep old certificates:** add entries to a product's `coa_history`; they
  appear as Archived rows in the COA library.
- **Product photos:** `public/assets/img/products/<slug>.webp`, taken from
  the live store. Replace a file (or add `.jpg`/`.png`) and rebuild; a product
  with no photo falls back to a generated vial render.
- **Pages and copy:** `src/pages/*.html`. The top banner is in
  `src/layout.html`.
- **Pricing rules** (free-shipping threshold, flat rate, promo code) live in
  `backend/app/config.py`, which is authoritative. Mirror changes in `CONFIG`
  in `public/assets/js/store.js` (the cart preview) and in the banner copy.

## Design

Layout, palette and section order follow the live vrcsolutions.co theme:
cream page with framed 1200px sections alternating deep teal, beige, cream and
white; copper actions; Inter headings. Tokens are in
`public/assets/css/tokens.css` (`--teal #0F3433`, `--copper #B8794A`,
`--cream #F7F4ED`, `--beige #EDE6D4`). Page templates reuse a small set of
components in `public/assets/css/vrc.css`: `.shell.sec` sections, `.page-hero`,
`.pcard` product cards, `.coa-table`, `.faq-item`, `.panel`. The homepage
photo cards use Unsplash images (free licence), self-hosted in
`public/assets/img/why/`.

### v2 visual layer (redesign branch)

`public/assets/css/fx.css` and `public/assets/js/fx.js` sit on top of the
base design. Sections with the `fx-glow` class (home hero, page headers, the
product photo stage) get a drifting glow and a particle canvas that pauses
off-screen. Product cards and product pages use background-free vials from
`public/assets/img/cutouts/<slug>.webp` when one exists, else the photo.
Hover effects are reserved for clickable things; everything else fades in
once on scroll. All motion is off for visitors who prefer reduced motion.

## Backend and integrations — placeholders

The old site had connections this rebuild can only infer. Each is an adapter
in `backend/app/integrations/`. The rest of the app calls only those modules,
so replacing an adapter never touches routes or pages. Anything not connected
raises a clear "not connected" error instead of failing silently.

| Module | Today | Replace with |
|---|---|---|
| `payments.py` manual | **Live**: Venmo, Cash App, wallet addresses with order reference | — |
| `payments.py` card | Placeholder: customer is told to email | The old site's card processor |
| `payments.py` crypto | Placeholder: manual wallet addresses work now | Optional crypto processor |
| `shipping.py` | Placeholder: admin enters tracking by hand | Label/tracking provider |
| `email.py` | SMTP works when configured; logs otherwise | Transactional provider, if any |
| `woocommerce.py` | Fetches products/customers/orders/coupons via WooCommerce REST API | Mapping into this app's models |
| `marketing.py` | Placeholder (unconfirmed the old site had these) | Analytics, newsletter |

Check status: `GET /api/admin/integrations`. Inbound provider webhooks arrive
at `POST /api/webhooks/{card|crypto|shipping}`.

Not rebuilt yet: **customer accounts**. The old site had `/my-account/`; this
one uses guest checkout plus an order-status lookup (`/order-status/`).
Accounts can be added once the original user data and requirements are known.

## Admin API

All admin routes need `Authorization: Bearer $ADMIN_TOKEN`.

```bash
API=http://localhost:8000/api; H="Authorization: Bearer $ADMIN_TOKEN"
curl -H "$H" $API/admin/orders                              # list orders
curl -H "$H" -X PATCH $API/admin/orders/VRC-ABC123 \
     -H 'Content-Type: application/json' -d '{"status":"paid"}'
curl -H "$H" -X PATCH $API/admin/orders/VRC-ABC123 \
     -H 'Content-Type: application/json' \
     -d '{"status":"shipped","tracking_number":"9400...","notify":true}'
curl -H "$H" -X PATCH $API/admin/products/TB10/coa \
     -H 'Content-Type: application/json' \
     -d '{"lot":"TB10-0926","coa_url":"https://...","purity":"99.1%"}'
curl -H "$H" $API/admin/messages                            # contact form inbox
curl -H "$H" $API/admin/integrations                        # what's live
```

An admin change to a product's COA updates the database only; mirror it in
`data/products.json` and rebuild so the pages match.

## Before launch

`python3 build.py --strict` refuses to build while any of the data items
below is open.

**Catalog data** (every figure on this site is a claim about a lab result):
- [ ] Publish COAs for TB-500, MOTS-c, Selank, Semax, Glutathione, Bac Water 3ml/10ml, BioWater
      (the live COA library now lists certificates for some of these; reconcile them)
- [ ] Real lot numbers for the products showing "Not published"
- [ ] Exact purity, method and test date from each certificate (unconfirmed products show only "≥99%")
- [ ] Confirm the blend compositions (GLW70, KLW80)
- [ ] Confirm molecular weights (TB-500 in particular: fragment vs full-length)

**Content:**
- [x] Terms, refund, privacy and RUO policy text, copied from the live site
- [ ] Legal review of those four pages. The live Terms' "International Orders"
      and "Customs Duties and VAT" sections were left out because checkout is
      US-only; restore them if that changes
- [x] Learn page migrated from the live site
- [x] Product photos (from the live store)

**Configuration:**
- [ ] `ADMIN_TOKEN`, `IP_HASH_SALT`, `CORS_ORIGINS`
- [ ] Venmo and Cash App handles, BTC/ETH/USDC addresses
- [ ] SMTP (or email provider) so customers get confirmations
- [ ] Integrations from the original backend (table above)

## Compliance notes

The site sells research-use-only materials and is written to keep it that
way: no dosing, reconstitution or human-use content anywhere. The RUO gate
logs acknowledgments (hashed IP, no personal data), checkout requires an
explicit RUO confirmation that the server enforces, and each order line
records the lot that shipped.
