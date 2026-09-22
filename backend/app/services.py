"""Business logic: pricing, payment instructions, email.

Pricing lives here rather than in a route handler because it is the one piece
of logic the storefront also implements (as a preview). Keeping it in a single
function makes the two easy to keep in step — and the server's answer is the
only one that counts.
"""

import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy.orm import Session

from .config import settings
from .models import Order, Product

log = logging.getLogger("vrc")


class PricingError(ValueError):
    """Raised when a cart references something unsellable."""


def price_cart(db: Session, items: list, promo_code: str | None) -> dict:
    """Recompute every figure from the database.

    The browser sends SKUs and quantities. It does not get to send prices.
    """
    if not items:
        raise PricingError("Your cart is empty.")

    skus = [i.sku for i in items]
    found = {p.sku: p for p in db.query(Product).filter(Product.sku.in_(skus)).all()}

    lines, subtotal_cents, notices = [], 0, []

    for item in items:
        product = found.get(item.sku)
        if product is None:
            raise PricingError(f"{item.sku} is no longer in the catalog.")
        if not product.in_stock:
            raise PricingError(f"{product.name} is out of stock.")

        qty = max(1, min(item.qty, settings.max_qty_per_line))
        if qty != item.qty:
            notices.append(f"Quantity for {product.name} adjusted to {qty}.")

        line_cents = product.price_cents * qty
        subtotal_cents += line_cents
        lines.append({
            "sku": product.sku,
            "name": product.name,
            "unit_price": product.price_cents / 100,
            "qty": qty,
            "line_total": line_cents / 100,
            "_product": product,
        })

    promo_applied = bool(promo_code) and promo_code.strip().upper() == settings.promo_code
    # Integer half-up rounding at the cent. No floats touch money here, and the
    # rule matches the browser preview in store.js exactly.
    discount_cents = (subtotal_cents * settings.promo_percent + 50) // 100 if promo_applied else 0
    if promo_code and not promo_applied:
        notices.append(f"Code '{promo_code}' was not recognised and has not been applied.")

    after_discount = subtotal_cents - discount_cents

    # Threshold is checked against the discounted figure, so the promo cannot
    # be used to cross the free-shipping line. store.js mirrors this exactly.
    threshold_cents = round(settings.free_shipping_threshold * 100)
    shipping_cents = 0 if after_discount >= threshold_cents else round(settings.flat_shipping * 100)

    return {
        "items": lines,
        "subtotal": subtotal_cents / 100,
        "discount": discount_cents / 100,
        "shipping": shipping_cents / 100,
        "total": (after_discount + shipping_cents) / 100,
        "promo_applied": promo_applied,
        "free_shipping_remaining": max(0, threshold_cents - after_discount) / 100,
        "notices": notices,
        "_cents": {
            "subtotal": subtotal_cents,
            "discount": discount_cents,
            "shipping": shipping_cents,
            "total": after_discount + shipping_cents,
        },
    }


def payment_instructions(method: str, reference: str, total: float) -> dict:
    """What the customer needs in order to pay.

    Venmo, Cash App and crypto are manual rails, so the reference code is the
    only thing tying a payment back to an order. It goes in every instruction.
    """
    amount = f"${total:,.2f}"
    common = {
        "reference": reference,
        "amount": amount,
        "note": f"Include {reference} in the payment note so we can match it to your order.",
    }

    if method == "venmo":
        return {**common, "method": "Venmo", "handle": settings.venmo_handle or "PLACEHOLDER — set VENMO_HANDLE in .env"}
    if method == "cashapp":
        return {**common, "method": "Cash App", "handle": settings.cashapp_handle or "PLACEHOLDER — set CASHAPP_HANDLE in .env"}
    if method == "crypto":
        return {
            **common,
            "method": "Cryptocurrency",
            "addresses": {
                "BTC": settings.btc_address or "PLACEHOLDER — set BTC_ADDRESS in .env",
                "ETH": settings.eth_address or "PLACEHOLDER — set ETH_ADDRESS in .env",
                "USDC": settings.usdc_address or "PLACEHOLDER — set USDC_ADDRESS in .env",
            },
            "note": "Send the exact amount, then reply to your confirmation email with the transaction hash.",
        }
    if method == "card":
        return create_card_intent(reference, total)
    return common


def create_card_intent(reference: str, total: float) -> dict:
    """PLACEHOLDER — card processing.

    Delegates to integrations.payments. Until a processor is connected the
    route accepts 'card' and tells the customer to get in touch.
    """
    from .integrations import NotConfigured, payments
    try:
        return payments.create_card_payment(reference, round(total * 100), "")
    except (NotConfigured, NotImplementedError):
        pass
    return {
        "method": "Card",
        "reference": reference,
        "amount": f"${total:,.2f}",
        "status": "unavailable",
        "note": (
            "Card payment is enabled for select regions only. "
            "Email orders@vrcsolutions.co and we will confirm whether yours is covered."
        ),
    }


def send_email(to: str, subject: str, body: str) -> bool:
    """Send if SMTP is configured, otherwise log.

    Email failure must never lose an order — the order row is already committed
    by the time this runs, and the reference code is in the API response.
    """
    if not settings.smtp_host:
        log.info("[email not configured] to=%s subject=%s\n%s", to, subject, body)
        return False

    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
        return True
    except Exception:
        log.exception("Failed to send email to %s", to)
        return False


def order_confirmation_body(order: Order, instructions: dict) -> str:
    lines = "\n".join(
        f"  {i.qty} x {i.name} ({i.sku})  ${i.unit_price_cents * i.qty / 100:,.2f}"
        for i in order.items
    )
    payment = "\n".join(f"  {k}: {v}" for k, v in instructions.items() if isinstance(v, str))
    return f"""Thanks for your order.

Reference: {order.reference}

{lines}

Subtotal   ${order.subtotal_cents / 100:,.2f}
Discount  -${order.discount_cents / 100:,.2f}
Shipping   ${order.shipping_cents / 100:,.2f}
Total      ${order.total_cents / 100:,.2f}

How to pay
{payment}

Your order ships the next business day once payment clears. You will get a
tracking number by email.

All products are sold for laboratory research use only. They are not for human
or animal consumption and have not been evaluated by the FDA.

VRC Solutions LLC
9462 Brownsboro Rd, PMB 379, Louisville, KY 40241
"""
