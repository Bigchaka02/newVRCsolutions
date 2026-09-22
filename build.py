#!/usr/bin/env python3
"""
build.py — static site generator for VRC Solutions.

Reads data/products.json and the templates in src/, and writes a complete,
deployable site into public/. Run it after any content or catalog change:

    python3 build.py

Why pre-render instead of fetching products in the browser: product pages are
the pages that need to rank. Real HTML means crawlers, link previews and no-JS
visitors all get the full page, with no loading spinner on the highest-intent
page on the site.

URLs deliberately match the live WordPress site (/shop/, /faq/,
/product/<slug>/) so existing rankings and inbound links carry over with no
redirect hop. The handful of WordPress URLs that no longer exist are listed in
LEGACY_REDIRECTS and written to public/_redirects.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
SRC = ROOT / "src"
OUT = ROOT / "public"
DATA = json.loads((ROOT / "data" / "products.json").read_text(encoding="utf-8"))

SITE = DATA["site"]
PRODUCTS = DATA["products"]
CATEGORIES = {c["slug"]: c["name"] for c in DATA["categories"]}
BASE = SITE["base_url"].rstrip("/")
API_BASE = SITE.get("api_base", "").rstrip("/")
YEAR = date.today().year

# Sub-path the site is served from, e.g. "/newVRCsolutions" on GitHub Pages.
# Empty for the real domain. Set with --base-path; see main().
SUBPATH = ""
ROOT_LINK = re.compile(r'\b(href|src|action)="/(?!/)')

FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
IMG_DIR = OUT / "assets" / "img" / "products"

# Old WordPress URLs with no one-to-one page on the new site. Everything else
# keeps its original address. Both slash variants, because WordPress served
# both and inbound links use both.
LEGACY_REDIRECTS = {
    "/cart/": "/checkout/",
    "/my-account/": "/order-status/",
    "/terms-of-service/": "/terms-conditions/",
    "/shop/page/2/": "/shop/",
    "/product-category/peptides/": "/shop/#peptides",
    "/product-category/research-solvents/": "/shop/#solvents",
    "/product-category/solvents/": "/shop/#solvents",
    "/product-category/uncategorized/": "/shop/",
}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def e(value) -> str:
    """Escape for HTML text and double-quoted attributes."""
    return html.escape(str(value), quote=True)


def attr_json(obj) -> str:
    """JSON safe to embed in a single-quoted HTML attribute."""
    return json.dumps(obj, separators=(",", ":")).replace("'", "&#39;")


def money(n) -> str:
    return f"${n:,.2f}"


def nice_date(iso: str) -> str:
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d %b %Y")
    except (ValueError, TypeError):
        return iso or "—"


def is_placeholder_lot(lot: str | None) -> bool:
    return not lot or lot.startswith("PLACEHOLDER")


def purity_confirmed(p: dict) -> bool:
    return p.get("purity_method", "") not in ("", "See COA")


def purity_text(p: dict, html_out: bool = True) -> str:
    """'99.24% by HPLC-UV' when the figure is confirmed from the certificate;
    otherwise only the site-wide claim, never a number nobody measured."""
    purity = p.get("purity", "—")
    if purity_confirmed(p):
        num = f'<span class="purity mono">{e(purity)}</span>' if html_out else purity
        return f"{num} by {e(p['purity_method']) if html_out else p['purity_method']}"
    num = f'<span class="purity mono">{e(purity)}</span>' if html_out else purity
    return f"{num} (exact figure on the certificate)"


def parse_front_matter(raw: str) -> tuple[dict, str]:
    meta: dict = {}
    match = FRONT_MATTER.match(raw)
    if not match:
        return meta, raw
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
    return meta, raw[match.end():]


def out_path(url_path: str) -> Path:
    """/shop/ -> public/shop/index.html, / -> public/index.html."""
    clean = url_path.strip("/")
    return OUT / clean / "index.html" if clean else OUT / "index.html"


# --------------------------------------------------------------------------
# product imagery
# --------------------------------------------------------------------------

def label_name(p: dict) -> str:
    if p.get("label"):
        return p["label"]
    name = re.sub(r"\s*\(.*?\)", "", p["name"])
    name = re.sub(r"\s*\d+(\.\d+)?\s*(mg|ml)\b.*$", "", name, flags=re.I)
    return name.replace(" Blend", "").strip()


def vial_svg(p: dict) -> str:
    """An original, uniform vial render used until a real photo exists.

    Clearly a stand-in, but a consistent one, so the catalog reads as
    intentional rather than as 22 grey boxes. Colours are literal because an
    SVG loaded through <img> cannot see the page's CSS variables.
    """
    name = label_name(p)
    mass = p.get("mass", "").split(" ")[0]
    size = min(28, round(150 / (0.62 * max(len(name), 1))))
    # Glyph widths vary by the viewer's fallback font, so long names get an
    # explicit textLength: they compress to fit, never spill past the label.
    est = 0.6 * size * len(name)
    fit = f' textLength="{round(min(est, 128))}" lengthAdjust="spacingAndGlyphs"' if est > 105 else ""
    lot = "" if is_placeholder_lot(p.get("lot")) else f"LOT {p['lot']}"
    solvent = p["category"] == "solvents"

    contents = (
        # liquid for solvents
        '<rect x="134" y="262" width="132" height="182" rx="18" fill="#CFE3E1" fill-opacity=".75"/>'
        '<rect x="134" y="262" width="132" height="4" fill="#9EC5C1" fill-opacity=".8"/>'
        if solvent else
        # lyophilised cake for peptides and blends
        '<path d="M137 406 Q200 388 263 406 L263 430 Q263 442 251 442 L149 442 '
        'Q137 442 137 430 Z" fill="#F3ECDC" stroke="#E2D7BF" stroke-width="1.5"/>'
    )

    lot_line = (
        f'<text x="200" y="344" text-anchor="middle" font-family="Menlo,Consolas,monospace" '
        f'font-size="9.5" fill="#966922" letter-spacing=".4">{e(lot)}</text>'
        if lot else ""
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 500" role="img" aria-label="{e(p['name'])} vial">
  <ellipse cx="200" cy="454" rx="92" ry="10" fill="#123D3C" fill-opacity=".10"/>
  <rect x="146" y="116" width="108" height="42" rx="6" fill="#FFFFFF" fill-opacity=".55" stroke="#123D3C" stroke-opacity=".22" stroke-width="2"/>
  <rect x="128" y="150" width="144" height="300" rx="22" fill="#FFFFFF" fill-opacity=".55" stroke="#123D3C" stroke-opacity=".22" stroke-width="2"/>
  {contents}
  <rect x="140" y="162" width="8" height="268" rx="4" fill="#FFFFFF" fill-opacity=".7"/>
  <rect x="138" y="94" width="124" height="30" rx="5" fill="#C9CECC"/>
  <rect x="138" y="110" width="124" height="2" fill="#AEB4B2"/>
  <rect x="146" y="68" width="108" height="30" rx="8" fill="#123D3C"/>
  <rect x="128" y="220" width="144" height="152" fill="#F7F4ED" stroke="#123D3C" stroke-opacity=".18"/>
  <rect x="128" y="220" width="144" height="26" fill="#123D3C"/>
  <text x="200" y="238" text-anchor="middle" font-family="Menlo,Consolas,monospace" font-size="12" font-weight="700" fill="#F7F4ED" letter-spacing="2">VRC</text>
  <text x="200" y="290" text-anchor="middle" font-family="Helvetica Neue,Helvetica,Arial,sans-serif" font-size="{size}" font-weight="700" fill="#0E2B2A"{fit}>{e(name)}</text>
  <text x="200" y="314" text-anchor="middle" font-family="Helvetica Neue,Helvetica,Arial,sans-serif" font-size="15" fill="#4A6664">{e(mass)}</text>
  <line x1="148" y1="327" x2="252" y2="327" stroke="#B4802F" stroke-width="1.5"/>
  {lot_line}
  <text x="200" y="362" text-anchor="middle" font-family="Helvetica Neue,Helvetica,Arial,sans-serif" font-size="7.5" font-weight="700" fill="#8C2F26" letter-spacing="1.2">RESEARCH USE ONLY</text>
</svg>
"""


def resolve_images() -> list[str]:
    """Point each product at a real photo if one exists, else a generated vial.

    Drop bpc-157-10mg.webp (or .jpg / .png) into public/assets/img/products/
    and the next build picks it up automatically.
    """
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    placeholders = []
    for p in PRODUCTS:
        stem = Path(p.get("image") or p["slug"]).stem
        real = next(
            (IMG_DIR / f"{stem}{ext}" for ext in (".webp", ".jpg", ".jpeg", ".png")
             if (IMG_DIR / f"{stem}{ext}").exists()),
            None,
        )
        if real:
            p["_img"] = "/" + real.relative_to(OUT).as_posix()
        else:
            target = IMG_DIR / f"{p['slug']}.svg"
            target.write_text(vial_svg(p), encoding="utf-8")
            p["_img"] = "/" + target.relative_to(OUT).as_posix()
            placeholders.append(p["sku"])
    return placeholders


# --------------------------------------------------------------------------
# fragments
# --------------------------------------------------------------------------

def coa_button(url: str) -> str:
    return (f'<a class="btn btn-verify btn-sm" href="{e(url)}" '
            f'target="_blank" rel="noopener">View COA</a>')


def ledger_row(p: dict, record: dict | None = None, archived: bool = False) -> str:
    """One row of the batch ledger. `record` is an archived lot when given.

    The old site sent products with no certificate to /coa-library/, which
    quietly broke the site's central promise. A missing certificate is now
    stated as Pending instead of being disguised as a working link.
    """
    r = record or p
    lot = r.get("lot", "")
    url = r.get("coa_url", "")
    search = " ".join([p["sku"], p["name"], p["compound"], lot, p["category"]]).lower()
    lot_html = ('<span class="muted">Not published</span>' if is_placeholder_lot(lot)
                else f'<span class="mono">{e(lot)}</span>')
    tag = ' <span class="badge badge-plain">Archived</span>' if archived else ""
    cert = coa_button(url) if url else (
        '<span class="badge badge-plain" title="Certificate not yet published">Pending</span>')
    return f"""          <tr data-search="{e(search)}">
            <td class="mono">{e(p['sku'])}</td>
            <td><a class="ledger-name" href="/product/{e(p['slug'])}/">{e(p['name'])}</a>{tag}</td>
            <td>{lot_html}</td>
            <td class="purity mono">{e(r.get('purity', '—'))}</td>
            <td>{e(r.get('purity_method', '—'))}</td>
            <td>{e(nice_date(r.get('tested', '')))}</td>
            <td style="text-align:right">{cert}</td>
          </tr>"""


def card(p: dict, order: int) -> str:
    payload = {"sku": p["sku"], "slug": p["slug"], "name": p["name"],
               "price": p["price"], "image": p["_img"]}
    coa = (f'<a class="btn btn-verify btn-sm" href="{e(p["coa_url"])}" target="_blank" '
           f'rel="noopener" aria-label="View Certificate of Analysis for {e(p["name"])}">COA</a>'
           if p.get("coa_url") else "")
    return f"""      <article class="card" data-product
               data-category="{e(p['category'])}"
               data-name="{e(p['name'])}"
               data-sku="{e(p['sku'])}"
               data-compound="{e(p['compound'])}"
               data-lot="{e(p.get('lot',''))}"
               data-price="{p['price']}"
               data-order="{order}">
        <a class="card-media" href="/product/{e(p['slug'])}/" tabindex="-1" aria-hidden="true">
          <img src="{e(p['_img'])}" alt="" loading="lazy" width="320" height="400">
          <span class="badge badge-verify card-flag"><span class="dot"></span>{e(p.get('purity','—'))}</span>
        </a>
        <div class="card-body">
          <p class="card-cat">{e(CATEGORIES.get(p['category'], p['category'].title()))}</p>
          <h3 class="card-title"><a href="/product/{e(p['slug'])}/">{e(p['name'])}</a></h3>
          <p class="card-meta"><span class="mono">{e(p['sku'])}</span><span>{e(p['mass'])}</span></p>
          <div class="card-foot"><span class="card-price">{money(p['price'])}</span></div>
        </div>
        <div class="card-actions">
          <button class="btn btn-primary btn-sm" type="button" data-add='{attr_json(payload)}'>Add to cart</button>
          {coa}
        </div>
      </article>"""


def cards_html(items: list[dict]) -> str:
    return "\n".join(card(p, i) for i, p in enumerate(items))


# --------------------------------------------------------------------------
# structured data
# --------------------------------------------------------------------------

def jsonld(blocks: list[dict]) -> str:
    return "\n".join(
        '<script type="application/ld+json">' + json.dumps(b, separators=(",", ":")) + "</script>"
        for b in blocks
    )


ORGANISATION = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": SITE["legal_name"],
    "alternateName": SITE["name"],
    "url": BASE + "/",
    "email": SITE["email_general"],
    "address": {
        "@type": "PostalAddress",
        "streetAddress": SITE["address_line1"],
        "addressLocality": "Louisville",
        "addressRegion": "KY",
        "postalCode": "40241",
        "addressCountry": "US",
    },
    "sameAs": [SITE["instagram"], SITE["tiktok"]],
}


def product_jsonld(p: dict) -> dict:
    block = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": p["name"],
        "sku": p["sku"],
        "description": (f"{p['compound']} — research-grade reference material for "
                        f"laboratory research use only. Purity {purity_text(p, False)}."),
        "category": CATEGORIES.get(p["category"], p["category"]),
        "brand": {"@type": "Brand", "name": SITE["name"]},
        "image": BASE + p["_img"],
        "offers": {
            "@type": "Offer",
            "url": f"{BASE}/product/{p['slug']}/",
            "priceCurrency": "USD",
            "price": f"{p['price']:.2f}",
            "availability": ("https://schema.org/InStock" if p.get("stock")
                             else "https://schema.org/OutOfStock"),
            "seller": {"@type": "Organization", "name": SITE["legal_name"]},
        },
    }
    if not is_placeholder_lot(p.get("lot")):
        block["additionalProperty"] = [{"@type": "PropertyValue", "name": "Lot", "value": p["lot"]}]
        if purity_confirmed(p):
            block["additionalProperty"] += [
                {"@type": "PropertyValue", "name": "Purity", "value": p["purity"]},
                {"@type": "PropertyValue", "name": "Test method", "value": p["purity_method"]},
            ]
    return block


def breadcrumbs(trail: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": BASE + path}
            for i, (name, path) in enumerate(trail)
        ],
    }


def faq_jsonld(body: str) -> dict | None:
    """Lift the <details> blocks straight out of the FAQ markup, so the
    structured data can never drift from what the page actually says."""
    pairs = re.findall(r"<summary>(.*?)</summary>\s*<div class=\"acc-body\">(.*?)</div>", body, re.S)
    if not pairs:
        return None
    strip = lambda s: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": strip(q),
             "acceptedAnswer": {"@type": "Answer", "text": strip(a)}}
            for q, a in pairs
        ],
    }


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

LAYOUT = (SRC / "layout.html").read_text(encoding="utf-8")
PRODUCT_TPL = (SRC / "product.html").read_text(encoding="utf-8")
TOKENS: dict[str, str] = {}


def wrap_page(*, title, desc, path, content, ogtype="website",
              extra_ld=None, robots=None, gate="on") -> str:
    page = (LAYOUT
            .replace("{{TITLE}}", e(title))
            .replace("{{DESC}}", e(desc))
            .replace("{{PATH}}", path)
            .replace("{{BASE}}", BASE)
            .replace("{{API_BASE}}", e(API_BASE))
            .replace("{{OGTYPE}}", ogtype)
            .replace("{{GATE}}", "off" if gate == "off" else "on")
            .replace("{{YEAR}}", str(YEAR))
            .replace("{{JSONLD}}", jsonld([ORGANISATION] + (extra_ld or [])))
            .replace("{{CONTENT}}", content))
    if SUBPATH:
        # Served under a sub-path: prefix every root-relative link, including
        # the image path inside add-to-cart payloads. A sub-path host is never
        # the canonical site, so keep it out of search results.
        page = ROOT_LINK.sub(rf'\1="{SUBPATH}/', page).replace('"image":"/', f'"image":"{SUBPATH}/')
        robots = "noindex"
    if robots == "noindex":
        page = page.replace(
            '<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">',
            '<meta name="robots" content="noindex, follow">')
    return page


def substitute_tokens(body: str) -> str:
    for key, value in TOKENS.items():
        body = body.replace("{{" + key + "}}", value)
    return body


def build_pages() -> list[tuple[str, float]]:
    urls = []
    for src_file in sorted((SRC / "pages").glob("*.html")):
        meta, body = parse_front_matter(src_file.read_text(encoding="utf-8"))
        body = substitute_tokens(body)
        path = meta.get("path", f"/{src_file.stem}/")

        extra = []
        if path != "/":
            crumb = re.split(r"\s[—|]\s", meta.get("title", ""))[0].strip()
            extra.append(breadcrumbs([("Home", "/"), (crumb, path)]))
        if src_file.stem == "faq" and (block := faq_jsonld(body)):
            extra.append(block)

        target = out_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(wrap_page(
            title=meta.get("title", SITE["name"]), desc=meta.get("desc", ""),
            path=path, content=body, ogtype=meta.get("ogtype", "website"),
            extra_ld=extra, robots=meta.get("robots"), gate=meta.get("gate", "on"),
        ), encoding="utf-8")

        if meta.get("robots") != "noindex":
            urls.append((path, 1.0 if path == "/" else 0.7))
    return urls


def build_products() -> list[tuple[str, float]]:
    urls = []
    for p in PRODUCTS:
        related = [q for q in PRODUCTS if q["category"] == p["category"] and q["sku"] != p["sku"]][:4]
        related += [q for q in PRODUCTS if q["sku"] != p["sku"] and q not in related][: 4 - len(related)]

        payload = {"sku": p["sku"], "slug": p["slug"], "name": p["name"],
                   "price": p["price"], "image": p["_img"]}
        image = (f'<img src="{e(p["_img"])}" alt="{e(p.get("image_alt", p["name"]))}" '
                 f'width="560" height="700">')

        if p.get("coa_url"):
            coa = (f'<a class="btn btn-verify btn-block" href="{e(p["coa_url"])}" '
                   f'target="_blank" rel="noopener">Open the certificate</a>')
        else:
            # Honest about the gap rather than linking to a page that does not
            # contain the certificate.
            coa = ('<p class="small" style="color:var(--flag);font-weight:600">'
                   'The certificate for this lot is not yet published. '
                   '<a href="/contact/">Request it</a> and we will send it before you order.</p>')

        lot = "Not published" if is_placeholder_lot(p.get("lot")) else p["lot"]
        body = PRODUCT_TPL
        for key, value in {
            "P_NAME": e(p["name"]), "P_SKU": e(p["sku"]), "P_COMPOUND": e(p["compound"]),
            "P_MASS": e(p["mass"]), "P_MW": e(p["molecular_weight"]),
            "P_PURITY": e(p.get("purity", "—")), "P_PURITY_TEXT": purity_text(p),
            "P_METHOD_TEXT": (e(p["purity_method"]) if purity_confirmed(p) else "See certificate"),
            "P_LOT": e(lot), "P_TESTED": e(nice_date(p.get("tested", ""))),
            "P_STORAGE": e(p["storage"]), "P_PRICE_FMT": money(p["price"]),
            "P_CATEGORY_NAME": e(CATEGORIES.get(p["category"], p["category"].title())),
            "P_IMAGE": image, "P_COA_BUTTON": coa, "P_JSON": attr_json(payload),
            "P_RELATED": cards_html(related),
        }.items():
            body = body.replace("{{" + key + "}}", value)

        path = f"/product/{p['slug']}/"
        target = out_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(wrap_page(
            title=f"{p['name']} — {p.get('purity','')} Verified | VRC Solutions",
            desc=(f"{p['compound']} research reference material, {p['mass']}. "
                  f"Purity {purity_text(p, False)}. "
                  + ("Certificate of Analysis published. " if p.get("coa_url")
                     else "Certificate of Analysis available on request. ")
                  + "Research use only."),
            path=path, content=body, ogtype="product",
            extra_ld=[product_jsonld(p),
                      breadcrumbs([("Home", "/"), ("Shop", "/shop/"), (p["name"], path)])],
        ), encoding="utf-8")
        urls.append((path, 0.9))
    return urls


def content_security_policy() -> str:
    connect = "'self'"
    if API_BASE:
        parsed = urlparse(API_BASE)
        connect += f" {parsed.scheme}://{parsed.netloc}"
    # Nothing third-party loads: no inline scripts, fonts self-hosted.
    # 'unsafe-inline' on styles covers the style="" attributes in templates.
    return ("default-src 'self'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; img-src 'self' data:; "
            f"connect-src {connect}; form-action 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; object-src 'none'")


def build_meta_files(urls: list[tuple[str, float]]) -> None:
    today = date.today().isoformat()
    entries = "\n".join(
        f"  <url><loc>{BASE}{path}</loc><lastmod>{today}</lastmod><priority>{pri}</priority></url>"
        for path, pri in urls)
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n</urlset>\n", encoding="utf-8")

    (OUT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nDisallow: /checkout/\nDisallow: /order-status/\n"
        f"Disallow: /api/\n\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")

    # Cloudflare Pages and Netlify both read these two files natively.
    (OUT / "_headers").write_text(
        "/*\n"
        "  X-Content-Type-Options: nosniff\n"
        "  X-Frame-Options: DENY\n"
        "  Referrer-Policy: strict-origin-when-cross-origin\n"
        "  Permissions-Policy: geolocation=(), microphone=(), camera=()\n"
        "  Strict-Transport-Security: max-age=31536000; includeSubDomains\n"
        f"  Content-Security-Policy: {content_security_policy()}\n\n"
        "/assets/css/*\n  Cache-Control: public, max-age=3600, stale-while-revalidate=86400\n\n"
        "/assets/js/*\n  Cache-Control: public, max-age=3600, stale-while-revalidate=86400\n\n"
        "/assets/img/*\n  Cache-Control: public, max-age=2592000\n",
        encoding="utf-8")

    lines = ["# Legacy WordPress URLs -> new pages. Generated by build.py; edit LEGACY_REDIRECTS there."]
    for old, new in LEGACY_REDIRECTS.items():
        lines.append(f"{old}  {new}  301")
        lines.append(f"{old.rstrip('/')}  {new}  301")
    (OUT / "_redirects").write_text("\n".join(lines) + "\n", encoding="utf-8")

    (OUT / "catalog.json").write_text(json.dumps(
        {"products": [{k: v for k, v in p.items() if not k.startswith("_")} for p in PRODUCTS],
         "categories": DATA["categories"]}, indent=2), encoding="utf-8")

    (OUT / "assets" / "img" / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="10" fill="#123D3C"/>'
        '<text x="32" y="41" font-family="Menlo,Consolas,monospace" font-size="21" '
        'font-weight="700" fill="#F7F4ED" text-anchor="middle">VRC</text></svg>',
        encoding="utf-8")

    (OUT / "404.html").write_text(wrap_page(
        title="Page not found | VRC Solutions", desc="That page does not exist.",
        path="/404.html", robots="noindex", gate="off",
        content="""
<section class="wrap band">
  <div class="head-block">
    <h1>That page doesn't exist</h1>
    <p class="lead">The link may be out of date. The catalog and the full COA library are both one click away.</p>
  </div>
  <div class="btn-row">
    <a class="btn btn-primary" href="/shop/">Browse the catalog</a>
    <a class="btn btn-verify" href="/coa-library/">COA library</a>
  </div>
</section>"""), encoding="utf-8")


def clean() -> None:
    """Remove previously generated HTML, keep hand-made assets."""
    for stale in OUT.glob("*.html"):
        stale.unlink()
    shutil.rmtree(OUT / "product", ignore_errors=True)
    for src_file in (SRC / "pages").glob("*.html"):
        meta, _ = parse_front_matter(src_file.read_text(encoding="utf-8"))
        rel = meta.get("path", f"/{src_file.stem}/").strip("/")
        if rel:
            shutil.rmtree(OUT / rel, ignore_errors=True)
    for svg in IMG_DIR.glob("*.svg"):
        svg.unlink()


def main(strict: bool = False) -> None:
    clean()
    placeholders = resolve_images()

    current = [ledger_row(p) for p in PRODUCTS]
    archive = [ledger_row(p, rec, archived=True)
               for p in PRODUCTS for rec in p.get("coa_history", [])]

    TOKENS.update({
        "LEDGER_ROWS": "\n".join(current),
        "COA_LIBRARY_ROWS": "\n".join(current + archive),
        "FEATURED_CARDS": cards_html([p for p in PRODUCTS if p.get("featured")][:6]),
        "ALL_CARDS": cards_html(sorted(PRODUCTS, key=lambda p: (not p.get("featured"), p["name"]))),
        "PRODUCT_COUNT": str(len(PRODUCTS)),
    })

    urls = build_pages() + build_products()
    build_meta_files(urls)

    missing_coa = [p["sku"] for p in PRODUCTS if not p.get("coa_url")]
    missing_lot = [p["sku"] for p in PRODUCTS if is_placeholder_lot(p.get("lot"))]
    print(f"Built {len(urls)} indexable pages into {OUT}/ ({len(PRODUCTS)} products)")
    print(f"  {len(LEGACY_REDIRECTS) * 2} legacy redirects written to _redirects")
    if missing_coa:
        print(f"  WARNING  no COA for {len(missing_coa)} SKUs: {', '.join(missing_coa)}")
    if missing_lot:
        print(f"  WARNING  placeholder lot for {len(missing_lot)} SKUs: {', '.join(missing_lot)}")
    if placeholders:
        print(f"  NOTE     {len(placeholders)} products using generated vial renders "
              f"(add real photos to {IMG_DIR.relative_to(ROOT)}/)")

    # Every value on this site is a claim about a lab result. Anything not yet
    # confirmed against its certificate is listed in that product's "review"
    # field, and --strict refuses to build a deployable site until it's empty.
    pending = {p["sku"]: p["review"] for p in PRODUCTS if p.get("review")}
    if pending:
        print(f"  REVIEW   {len(pending)} products have unconfirmed fields:")
        for sku, fields in pending.items():
            print(f"             {sku:7s} {', '.join(fields)}")
    blockers = bool(pending or missing_coa or missing_lot)
    if strict and blockers:
        raise SystemExit("\nSTRICT BUILD FAILED: confirm every field above against its "
                         "certificate, clear each product's \"review\" list, then rebuild.")
    if strict:
        print("  STRICT   all products confirmed. Safe to deploy.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build the static site into public/.")
    parser.add_argument("--strict", action="store_true",
                        help="fail while any product has unconfirmed data")
    parser.add_argument("--base-path", default="",
                        help="serve under a sub-path, e.g. /newVRCsolutions for GitHub Pages")
    args = parser.parse_args()
    SUBPATH = "/" + args.base_path.strip("/") if args.base_path.strip("/") else ""
    main(strict=args.strict)
