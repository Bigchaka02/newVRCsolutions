"""Shipping. Placeholder for label purchase, rates and tracking, inferred
from the live site's 'ships next business day before 2pm ET, US only'.
Today the admin enters tracking numbers by hand (PATCH /api/admin/orders)."""

from __future__ import annotations

from .base import Integration, register

SHIPPING = register(Integration(
    "shipping.labels", "Shipping labels and tracking",
    "Buy labels, fetch rates, push tracking updates to orders.",
    "Live site shipping policy (US only, next business day)",
    ("shipping_provider", "shipping_api_key"),
))


def create_label(order_reference: str) -> dict:
    """PLACEHOLDER. Return {'tracking_number': ..., 'label_url': ...}."""
    SHIPPING.require()
    raise NotImplementedError


def track(tracking_number: str) -> dict:
    """PLACEHOLDER. Return the carrier's latest status."""
    SHIPPING.require()
    raise NotImplementedError


def handle_webhook(headers, body: bytes) -> None:
    """PLACEHOLDER. Update order status to shipped/delivered from carrier events."""
    SHIPPING.require()
