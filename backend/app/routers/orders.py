"""Order placement and status lookup."""

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Order, OrderItem
from ..schemas import OrderIn, OrderOut
from ..security import client_ip, hash_ip, limiter, order_reference
from ..services import (
    PricingError, order_confirmation_body, payment_instructions, price_cart, send_email,
)

router = APIRouter(tags=["orders"])


@router.post("/orders", response_model=OrderOut, status_code=201)
@limiter.limit("10/minute;60/hour")
def create_order(
    payload: OrderIn,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # Honeypot: a real person never fills a field they cannot see. Return 201
    # so the bot believes it succeeded and does not retry with a new strategy.
    if payload.website.strip():
        return OrderOut(
            reference=order_reference(), status="awaiting_payment",
            email=payload.email, subtotal=0, discount=0, shipping=0, total=0,
            payment_instructions={}, created_at=datetime.now(timezone.utc),
        )

    try:
        priced = price_cart(db, payload.items, payload.promo_code)
    except PricingError as err:
        raise HTTPException(400, str(err)) from err

    cents = priced["_cents"]
    reference = order_reference()

    order = Order(
        reference=reference,
        email=str(payload.email).lower(),
        name=payload.name.strip(),
        address1=payload.address1.strip(),
        address2=payload.address2.strip(),
        city=payload.city.strip(),
        state=payload.state,
        postal_code=payload.postal_code,
        payment_method=payload.payment_method,
        status="awaiting_payment",
        subtotal_cents=cents["subtotal"],
        discount_cents=cents["discount"],
        shipping_cents=cents["shipping"],
        total_cents=cents["total"],
        promo_code=payload.promo_code.upper() if priced["promo_applied"] else "",
        ruo_confirmed=True,
        ruo_confirmed_at=datetime.now(timezone.utc),
        ip_hash=hash_ip(client_ip(request)),
    )

    for line in priced["items"]:
        product = line["_product"]
        order.items.append(OrderItem(
            sku=line["sku"],
            name=line["name"],
            unit_price_cents=product.price_cents,
            qty=line["qty"],
            # Snapshot the lot so a refund or compliance query six months from
            # now can still identify which batch shipped.
            lot_at_purchase=product.lot,
        ))

    db.add(order)
    db.commit()
    db.refresh(order)

    instructions = payment_instructions(payload.payment_method, reference, order.total_cents / 100)

    # Sent after the response, so a slow mail server never delays checkout.
    background.add_task(
        send_email, order.email,
        f"Your VRC order {reference}",
        order_confirmation_body(order, instructions),
    )

    return OrderOut(
        reference=order.reference,
        status=order.status,
        email=order.email,
        subtotal=order.subtotal_cents / 100,
        discount=order.discount_cents / 100,
        shipping=order.shipping_cents / 100,
        total=order.total_cents / 100,
        payment_instructions=instructions,
        created_at=order.created_at,
    )


@router.get("/orders/{reference}")
@limiter.limit("20/minute")
def order_status(request: Request, reference: str, email: str, db: Session = Depends(get_db)):
    """Status lookup needs both the reference and the email used to order, so a
    guessed reference alone reveals nothing."""
    order = (
        db.query(Order)
        .filter(Order.reference == reference.upper(), Order.email == email.lower())
        .first()
    )
    if order is None:
        raise HTTPException(404, "No order matches that reference and email.")

    return {
        "reference": order.reference,
        "status": order.status,
        "total": order.total_cents / 100,
        "tracking_number": order.tracking_number,
        "placed": order.created_at,
        "items": [
            {"sku": i.sku, "name": i.name, "qty": i.qty, "lot": i.lot_at_purchase}
            for i in order.items
        ],
    }
