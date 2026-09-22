"""Payments. Manual rails (Venmo, Cash App, wallet addresses) are live today
via services.payment_instructions(). Card and crypto processors are
placeholders inferred from the live site ("cards in select regions",
BTC/ETH/USDC accepted)."""

from __future__ import annotations

import logging

from .base import Integration, register

log = logging.getLogger("vrc.payments")

MANUAL = register(Integration(
    "payments.manual", "Venmo / Cash App / wallet transfer",
    "Customer pays manually with the order reference in the note; admin marks paid.",
    "Live site payment options", implemented=True,
))
CARD = register(Integration(
    "payments.card", "Card processor",
    "Hosted checkout or payment intent for card payments in supported regions.",
    "Live site: 'cards accepted in select regions'",
    ("card_processor", "card_api_key", "card_webhook_secret"),
))
CRYPTO = register(Integration(
    "payments.crypto", "Crypto payment processor",
    "Optional: auto-detect BTC/ETH/USDC payments instead of manual confirmation.",
    "Live site: BTC, ETH, USDC accepted",
    ("crypto_processor", "crypto_api_key", "crypto_webhook_secret"),
))


def create_card_payment(reference: str, amount_cents: int, email: str) -> dict:
    """PLACEHOLDER. Return {'checkout_url': ...} or {'client_secret': ...}."""
    CARD.require()
    raise NotImplementedError  # replace with the original processor integration


def handle_card_webhook(headers, body: bytes) -> None:
    """PLACEHOLDER. Verify signature with CARD_WEBHOOK_SECRET, then mark the
    matching order 'paid' (see routers/admin.py for the status transition)."""
    CARD.require()


def handle_crypto_webhook(headers, body: bytes) -> None:
    """PLACEHOLDER. Same contract as the card webhook."""
    CRYPTO.require()
