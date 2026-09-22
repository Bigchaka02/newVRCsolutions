"""Integration layer: every external service the old WordPress/WooCommerce
site connected to, as a swappable adapter.

STATUS: placeholders inferred from the live site, pending the original
backend. The rest of the app calls only the functions in these modules, so
replacing an adapter's body never requires touching routes or templates.

Check what is live vs placeholder:  GET /api/admin/integrations
"""

from . import email, marketing, payments, shipping, woocommerce  # noqa: F401  (registers)
from .base import NotConfigured, registry, status_report

# Inbound webhooks, routed by /api/webhooks/{provider}.
WEBHOOKS = {
    "card": payments.handle_card_webhook,
    "crypto": payments.handle_crypto_webhook,
    "shipping": shipping.handle_webhook,
}

__all__ = ["NotConfigured", "registry", "status_report", "WEBHOOKS"]
