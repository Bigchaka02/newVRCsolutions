"""Marketing. Analytics and newsletter placeholders. Inferred, may not apply:
confirm against the original site before enabling. Any client-side tag also
needs its host added to content_security_policy() in build.py."""

from __future__ import annotations

import logging

from .base import Integration, register

log = logging.getLogger("vrc.marketing")

ANALYTICS = register(Integration(
    "marketing.analytics", "Analytics",
    "Page views and conversion events.", "Common WooCommerce setup (unconfirmed)",
    ("analytics_id",),
))
NEWSLETTER = register(Integration(
    "marketing.newsletter", "Newsletter / customer list",
    "Subscribe customers who opt in at checkout.", "Common WooCommerce setup (unconfirmed)",
    ("newsletter_provider", "newsletter_api_key"),
))


def track(event: str, **props) -> None:
    """Server-side event hook. Logs only until an analytics adapter exists."""
    log.info("event %s %s", event, props)


def subscribe(email: str) -> None:
    """PLACEHOLDER."""
    NEWSLETTER.require()
