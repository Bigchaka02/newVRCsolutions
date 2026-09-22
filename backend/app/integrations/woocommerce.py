"""WooCommerce import. One-time migration of data from the old WordPress
site (products, customers, orders, coupons) through the WooCommerce REST
API v3. Fetching works once keys are set; mapping into this app's models is
left open until the original backend and data shape are confirmed.

    cd backend && python -m app.integrations.woocommerce            # counts only
"""

from __future__ import annotations

import base64
import json
import urllib.request

from ..config import settings
from .base import Integration, register

WOO = register(Integration(
    "woocommerce.import", "WooCommerce data import",
    "Pull products, customers, orders and coupons from the old site.",
    "Live site runs WordPress + WooCommerce",
    ("woo_url", "woo_consumer_key", "woo_consumer_secret"),
    implemented=True,  # fetching is real; model mapping is the open part
))

RESOURCES = ("products", "customers", "orders", "coupons")


def fetch_all(resource: str, per_page: int = 100):
    """Yield every record of a WooCommerce resource, following pagination."""
    WOO.require()
    token = base64.b64encode(f"{settings.woo_consumer_key}:{settings.woo_consumer_secret}".encode()).decode()
    page = 1
    while True:
        url = f"{settings.woo_url.rstrip('/')}/wp-json/wc/v3/{resource}?per_page={per_page}&page={page}"
        req = urllib.request.Request(url, headers={"Authorization": f"Basic {token}"})
        with urllib.request.urlopen(req, timeout=30) as res:
            batch = json.loads(res.read())
        if not batch:
            return
        yield from batch
        page += 1


def import_all() -> dict:
    """PLACEHOLDER mapping: currently counts records per resource.
    TODO once the original backend is supplied: upsert into models.Product /
    Order, preserve WooCommerce order numbers, and migrate coupon rules."""
    return {r: sum(1 for _ in fetch_all(r)) for r in RESOURCES}


if __name__ == "__main__":
    print(import_all())
