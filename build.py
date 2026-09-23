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

import hashlib
import html
import json
import re
import shutil
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

import minify

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

# Readable styles and scripts live in src/assets/; build_assets() writes the
# minified copies that pages load. Stylesheets are joined in this order.
CSS_SOURCES = ("tokens.css", "vrc.css", "fx.css")

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


def is_solvent(p: dict) -> bool:
    return p["category"] == "solvents"


def strength(p: dict) -> str:
    """'10mg lyophilized (5mg + 5mg)' -> '10mg (5mg + 5mg)' for tables and cards."""
    return re.sub(r"\s*lyophili[sz]ed", "", p.get("mass", "")).strip()


def verify_pill(p: dict) -> str:
    """Card badge. Says 'Lab verified' only when a certificate is published;
    otherwise it says the certificate is pending, never implies one exists."""
    claim = "USP-grade solvent" if is_solvent(p) else f"{p.get('purity', '')} purity"
    if p.get("coa_url"):
        status, tone = ("Third-party tested" if is_solvent(p) else "Lab verified"), "pill-green"
    else:
        status, tone = "COA pending", "pill-amber"
    return f'<span class="pill {tone}">{e(claim)} · {status}</span>'


def svg(paths: str, width: str = "1.7") -> str:
    return (f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="{width}" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths}</svg>')


# Line icons, available to page templates as {{ICON_NAME}}.
ICONS = {
    "TRUCK": svg('<path d="M3 6h10v10H3z"/><path d="M13 9h4.2l3.3 3.6V16H13z"/>'
                 '<circle cx="7" cy="17" r="1.8"/><circle cx="17" cy="17" r="1.8"/>'),
    "SHIELD": svg('<path d="M12 3.2 5 6v5.3c0 4.4 3 8 7 9.5 4-1.5 7-5.1 7-9.5V6z"/><path d="m9 12.2 2.2 2.2 4-4.3"/>'),
    "BOX": svg('<path d="M12 3 20.5 7.5v9L12 21l-8.5-4.5v-9z"/><path d="M3.5 7.5 12 12l8.5-4.5M12 12v9"/>'),
    "GEM": svg('<path d="M7 4h10l4 5-9 11L3 9z"/><path d="M3 9h18M10 4 8.5 9 12 20l3.5-11L14 4"/>'),
    "FLASK": svg('<path d="M9 3h6M10 3v6L4.8 18.2A1.9 1.9 0 0 0 6.4 21h11.2a1.9 1.9 0 0 0 1.6-2.8L14 9V3"/><path d="M7 15h10"/>'),
    "DOC": svg('<rect x="5" y="3.5" width="14" height="17.5" rx="2"/><path d="M8.5 8.5h7M8.5 12.5h7M8.5 16.5h4"/>'),
    "BUILDING": svg('<path d="M4 21V6l8-3v18M12 9l8 2.5V21M2.5 21h19"/>'
                    '<path d="M7.5 9h1.5M7.5 12.5h1.5M7.5 16h1.5M15.5 14h1.5M15.5 17.5h1.5"/>'),
    "CHECK": svg('<path d="m5 12.5 4.5 4.5L19 7.5"/>', "2"),
    "X": svg('<path d="M7 7l10 10M17 7 7 17"/>', "2"),
    "BAN": svg('<circle cx="12" cy="12" r="9"/><path d="m5.7 5.7 12.6 12.6"/>'),
}


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

def ledger_row(p: dict, record: dict | None = None, archived: bool = False) -> str:
    """One row of the COA library table. `record` is an archived lot when given.

    The old site sent products with no certificate to /coa-library/, which
    quietly broke the site's central promise. A missing certificate is now
    stated as pending instead of being disguised as a working link.
    """
    r = record or p
    lot = r.get("lot", "")
    url = r.get("coa_url", "")
    search = " ".join([p["sku"], p["name"], p["compound"], lot, p["category"]]).lower()
    lot_html = ('<span class="muted xsmall">Not published</span>' if is_placeholder_lot(lot)
                else f'<span class="lot">{e(lot)}</span>')
    tag = ' <span class="pill pill-grey">Archived</span>' if archived else ""
    if is_solvent(p):
        purity = '<span class="pill pill-grey">USP</span>'
    else:
        tone = "pill-green" if url else "pill-amber"
        method = (f' <span class="xsmall muted">{e(r["purity_method"])}</span>'
                  if r.get("purity_method") not in (None, "", "See COA") else "")
        purity = f'<span class="pill {tone}">{e(r.get("purity", "—"))}</span>{method}'
    cert = (f'<a class="coa-btn" href="{e(url)}" target="_blank" rel="noopener" '
            f'aria-label="View COA for {e(p["name"])} lot {e(lot)}">View COA →</a>' if url else
            '<span class="coa-pending" title="Certificate not yet published">COA pending</span>')
    return f"""          <tr data-search="{e(search)}">
            <td class="cell-name"><a class="name" href="/product/{e(p['slug'])}/">{e(p['name'])}</a>{tag}</td>
            <td data-label="Strength">{e(strength(p))}</td>
            <td data-label="Lot number">{lot_html}</td>
            <td data-label="Purity">{purity}</td>
            <td class="cell-coa">{cert}</td>
          </tr>"""


CUTOUT_DIR = OUT / "assets" / "img" / "cutouts"


def cutout(p: dict) -> str:
    """Site path of the product's cut-out vial, or '' if there is none."""
    path = CUTOUT_DIR / f"{p['slug']}.webp"
    return "/" + path.relative_to(OUT).as_posix() if path.exists() else ""


def card(p: dict, order: int, solid: bool = False) -> str:
    """Product card: a dark glass card with the background-free cut-out vial
    from assets/img/cutouts/ when one exists. On dark sections the section
    shows through; `solid` gives the card its own teal ground for light
    sections (the shop)."""
    cut = cutout(p)
    img_src = cut or p["_img"]
    variant = (" pcard-show" + (" pcard-solid" if solid else "")) if cut else ""
    payload = {"sku": p["sku"], "slug": p["slug"], "name": p["name"],
               "price": p["price"], "image": p["_img"]}
    coa = (f'<a class="btn btn-coa" href="{e(p["coa_url"])}" target="_blank" rel="noopener" '
           f'aria-label="View Certificate of Analysis for {e(p["name"])}">COA</a>'
           if p.get("coa_url") else
           '<span class="btn btn-coa is-pending" title="Certificate for the current lot not yet published">COA pending</span>')
    return f"""      <article class="pcard{variant}" data-product
               data-category="{e(p['category'])}"
               data-name="{e(p['name'])}"
               data-sku="{e(p['sku'])}"
               data-compound="{e(p['compound'])}"
               data-lot="{e(p.get('lot',''))}"
               data-price="{p['price']}"
               data-order="{order}">
        <a class="pcard-media" href="/product/{e(p['slug'])}/" tabindex="-1" aria-hidden="true">
          <img src="{e(img_src)}" alt="" loading="lazy" width="640" height="800">
        </a>
        <div class="pcard-body">
          {verify_pill(p)}
          <p class="pcard-cat">{e(CATEGORIES.get(p['category'], p['category'].title()))}</p>
          <h3 class="pcard-title"><a href="/product/{e(p['slug'])}/">{e(p['name'])}</a></h3>
          <p class="pcard-price">{money(p['price'])}</p>
          <div class="pcard-actions">
            <button class="btn btn-copper btn-square btn-caps" type="button" data-add='{attr_json(payload)}'>Add to cart</button>
            {coa}
          </div>
        </div>
      </article>"""


def bestsellers() -> list[dict]:
    """The homepage row: site.bestsellers in the order given, else featured."""
    by_sku = {p["sku"]: p for p in PRODUCTS}
    picks = [by_sku[s] for s in SITE.get("bestsellers", []) if s in by_sku]
    return picks or [p for p in PRODUCTS if p.get("featured")][:4]


def cards_html(items: list[dict], solid: bool = False) -> str:
    return "\n".join(card(p, i, solid=solid) for i, p in enumerate(items))


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
    """Lift the question cards straight out of the FAQ markup, so the
    structured data can never drift from what the page actually says."""
    pairs = re.findall(r'<div class="faq-item"[^>]*>\s*<h3>(.*?)</h3>\s*<div class="answer">(.*?)</div>\s*</div>',
                       body, re.S)
    if not pairs:
        return None
    strip = lambda s: re.sub(r"\s+([.,;:!?])", r"\1",
                             re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()
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
ASSET_VERSION = ""


def build_assets() -> str:
    """Minify src/assets/ into public/assets/ and return a short content hash.

    Pages request every file with ?v=<hash>, and the modules import each other
    with it too, so a deploy never mixes old and new files from a cache."""
    css = minify.css("\n".join((SRC / "assets" / "css" / name).read_text(encoding="utf-8")
                               for name in CSS_SOURCES))
    scripts = {f.name: minify.js(f.read_text(encoding="utf-8"))
               for f in sorted((SRC / "assets" / "js").glob("*.js"))}
    digest = hashlib.sha256(css.encode())
    for name, code in scripts.items():
        digest.update(name.encode() + code.encode())
    version = digest.hexdigest()[:10]

    for kind in ("css", "js"):
        shutil.rmtree(OUT / "assets" / kind, ignore_errors=True)
        (OUT / "assets" / kind).mkdir(parents=True)
    (OUT / "assets" / "css" / "site.css").write_text(css, encoding="utf-8")
    for name, code in scripts.items():
        code = re.sub(r"""(from\s*'\./[\w-]+\.js)'""", rf"\1?v={version}'", code)
        (OUT / "assets" / "js" / name).write_text(code, encoding="utf-8")
    return version


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
            .replace("{{V}}", ASSET_VERSION)
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
    return minify.html(page)


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


def product_copy(p: dict) -> tuple[str, str]:
    """Short description and purity line for the buy box, in the live site's
    wording, but only claiming what the data confirms."""
    kind = "USP-grade research solvent" if is_solvent(p) else "high-purity research compound"
    short = f"<strong>{e(p['compound'])}</strong> — {kind} for laboratory research use only."
    has_coa = bool(p.get("coa_url"))
    if is_solvent(p):
        line = f"Grade: {e(p.get('purity', 'USP-grade'))}. Research-grade solvent for in-vitro laboratory dilution."
    elif purity_confirmed(p):
        line = (f"Lab verified: <strong>{e(p['purity'])}</strong> by {e(p['purity_method'])}. "
                "Independent third-party COA available.")
    else:
        line = f"Purity {e(p.get('purity', ''))}, exact figure on the certificate. "
        line += ("Independent third-party COA available." if has_coa
                 else "The certificate for the current lot is not yet published.")
    return short, line


def build_products() -> list[tuple[str, float]]:
    urls = []
    for p in PRODUCTS:
        related = [q for q in PRODUCTS if q["category"] == p["category"] and q["sku"] != p["sku"]][:4]
        related += [q for q in PRODUCTS if q["sku"] != p["sku"] and q not in related][: 4 - len(related)]

        payload = {"sku": p["sku"], "slug": p["slug"], "name": p["name"],
                   "price": p["price"], "image": p["_img"]}
        cut = cutout(p)
        image = (f'<img class="vial" src="{e(cut)}" alt="{e(p.get("image_alt", p["name"]))}" width="320" height="740">'
                 if cut else
                 f'<img src="{e(p["_img"])}" alt="{e(p.get("image_alt", p["name"]))}" width="640" height="800">')

        lot = "Not published" if is_placeholder_lot(p.get("lot")) else p["lot"]
        if p.get("coa_url"):
            coa_btn = (f'<a class="btn btn-green" href="{e(p["coa_url"])}" target="_blank" '
                       f'rel="noopener">View COA</a>')
            coa_panel = (f'<a class="btn btn-copper btn-block btn-square" href="{e(p["coa_url"])}" '
                         f'target="_blank" rel="noopener">Open the certificate</a>'
                         '<p class="note">Opens the laboratory report for this lot in a new tab.</p>')
            coa_status = '<span class="pill pill-green"><span class="dot"></span>COA published</span>'
        else:
            # Honest about the gap rather than linking to a page that does not
            # contain the certificate.
            coa_btn = '<a class="btn btn-outline" href="/contact/">Request COA</a>'
            coa_panel = ('<a class="btn btn-outline btn-block btn-square" href="/contact/">Request the certificate</a>'
                         '<p class="note">The certificate for this lot is not yet published. '
                         'Ask and we will send it before you order.</p>')
            coa_status = '<span class="pill pill-amber"><span class="dot"></span>COA pending</span>'

        spec_rows = [("Compound", e(p["compound"])), ("Molecular weight", e(p["molecular_weight"])),
                     ("Mass", e(p["mass"])), ("Storage", e(p["storage"])),
                     ("Purity", purity_text(p)), ("Lot", f'<span class="mono">{e(lot)}</span>')]
        specs = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in spec_rows)
        short, purity_line = product_copy(p)

        body = PRODUCT_TPL
        for key, value in {
            "P_NAME": e(p["name"]), "P_SKU": e(p["sku"]),
            "P_PURITY": e(p.get("purity", "—")),
            "P_METHOD_TEXT": (e(p["purity_method"]) if purity_confirmed(p) else "See certificate"),
            "P_LOT": e(lot), "P_TESTED": e(nice_date(p.get("tested", ""))),
            "P_PRICE_FMT": money(p["price"]),
            "P_CATEGORY_NAME": e(CATEGORIES.get(p["category"], p["category"].title())),
            "P_CATEGORY_SLUG": e(p["category"]),
            "P_SHORT": short, "P_PURITY_LINE": purity_line,
            "P_STOCK": ('<span class="in-stock">In stock</span>' if p.get("stock", True)
                        else '<span class="muted">Out of stock</span>'),
            "P_IMAGE": image, "P_COA_BUTTON": coa_btn, "P_COA_PANEL": coa_panel,
            "P_COA_STATUS": coa_status, "P_SPECS": specs, "P_JSON": attr_json(payload),
            "P_RELATED": "\n".join(card(q, i) for i, q in enumerate(related)),
        }.items():
            body = body.replace("{{" + key + "}}", value)
        body = substitute_tokens(body)

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
        # CSS and JS are requested with ?v=<content hash>, so they can be cached for good.
        "/assets/css/*\n  Cache-Control: public, max-age=31536000, immutable\n\n"
        "/assets/js/*\n  Cache-Control: public, max-age=31536000, immutable\n\n"
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
        '<rect width="64" height="64" rx="12" fill="#0F3433"/>'
        '<rect x="12" y="14" width="2.5" height="36" rx="1" fill="#B8794A"/>'
        '<text x="37" y="41" font-family="Helvetica,Arial,sans-serif" font-size="20" '
        'font-weight="800" fill="#F7F4ED" text-anchor="middle">VRC</text></svg>',
        encoding="utf-8")

    (OUT / "404.html").write_text(wrap_page(
        title="Page not found | VRC Solutions", desc="That page does not exist.",
        path="/404.html", robots="noindex", gate="off",
        content="""
<section class="shell sec sec-dark page-hero fx-glow">
  <div class="inner-narrow">
    <p class="tagline">Error 404</p>
    <h1>That page doesn't exist.</h1>
    <span class="rule"></span>
    <p class="lead">The link may be out of date. The catalog and the full COA library are both one click away.</p>
    <div class="btn-row">
      <a class="btn btn-copper btn-lg" href="/shop/">Browse the catalog</a>
      <a class="btn btn-light btn-lg" href="/coa-library/">COA Library</a>
    </div>
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
    global ASSET_VERSION
    clean()
    ASSET_VERSION = build_assets()
    placeholders = resolve_images()

    current = [ledger_row(p) for p in PRODUCTS]
    archive = [ledger_row(p, rec, archived=True)
               for p in PRODUCTS for rec in p.get("coa_history", [])]

    TOKENS.update({
        "LEDGER_ROWS": "\n".join(current),
        "COA_LIBRARY_ROWS": "\n".join(current + archive),
        "FEATURED_CARDS": "\n".join(card(p, i) for i, p in enumerate(bestsellers())),
        "ALL_CARDS": cards_html(sorted(PRODUCTS, key=lambda p: (not p.get("featured"), p["name"])), solid=True),
        "PRODUCT_COUNT": str(len(PRODUCTS)),
        "COUNT_PEPTIDES": str(sum(p["category"] == "peptides" for p in PRODUCTS)),
        "COUNT_SOLVENTS": str(sum(p["category"] == "solvents" for p in PRODUCTS)),
        **{f"ICON_{name}": icon for name, icon in ICONS.items()},
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
