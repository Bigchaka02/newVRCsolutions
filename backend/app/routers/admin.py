"""Admin endpoints. Bearer token from ADMIN_TOKEN.

A token in a header is adequate for a single operator. If more than one person
needs access, replace require_admin with real accounts and sessions before
handing the token around.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..integrations import status_report
from ..models import ContactMessage, Order, Product
from ..schemas import Ok
from ..security import require_admin
from ..services import send_email

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

STATUSES = {"awaiting_payment", "paid", "packed", "shipped", "delivered", "cancelled", "refunded"}


class StatusUpdate(BaseModel):
    status: str
    tracking_number: str = Field(default="", max_length=80)
    notify: bool = True


class CoaUpdate(BaseModel):
    """Rotating a lot is the most common catalog edit, so it gets its own
    endpoint — update the lot and its certificate together, atomically."""

    lot: str = Field(min_length=1, max_length=80)
    coa_url: str = Field(min_length=1, max_length=1000)
    purity: str = Field(default="", max_length=32)
    purity_method: str = Field(default="", max_length=40)
    tested_on: str = Field(default="", max_length=20)


@router.get("/orders")
def list_orders(db: Session = Depends(get_db), status: str | None = None, limit: int = 100):
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == status)
    orders = query.order_by(Order.created_at.desc()).limit(min(limit, 500)).all()
    return [
        {
            "reference": o.reference, "status": o.status, "email": o.email,
            "name": o.name, "total": o.total_cents / 100,
            "payment_method": o.payment_method, "tracking": o.tracking_number,
            "placed": o.created_at,
            "items": [{"sku": i.sku, "qty": i.qty, "lot": i.lot_at_purchase} for i in o.items],
        }
        for o in orders
    ]


@router.patch("/orders/{reference}", response_model=Ok)
def update_status(reference: str, payload: StatusUpdate, db: Session = Depends(get_db)):
    if payload.status not in STATUSES:
        raise HTTPException(400, f"Status must be one of: {', '.join(sorted(STATUSES))}")

    order = db.query(Order).filter(Order.reference == reference.upper()).first()
    if order is None:
        raise HTTPException(404, "No order with that reference.")

    order.status = payload.status
    if payload.tracking_number:
        order.tracking_number = payload.tracking_number
    db.commit()

    if payload.notify and payload.status == "shipped":
        send_email(
            order.email,
            f"Your VRC order {order.reference} has shipped",
            f"Tracking: {order.tracking_number or 'to follow'}\n\n"
            "Research use only. Not for human or animal consumption.\n",
        )

    return Ok(detail=f"{order.reference} set to {payload.status}.")


@router.patch("/products/{sku}/coa", response_model=Ok)
def update_coa(sku: str, payload: CoaUpdate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.sku == sku.upper()).first()
    if product is None:
        raise HTTPException(404, "No product with that SKU.")

    product.lot = payload.lot
    product.coa_url = payload.coa_url
    product.coa_type = "lab" if "janoshik" in payload.coa_url.lower() else "image"
    if payload.purity:
        product.purity = payload.purity
    if payload.purity_method:
        product.purity_method = payload.purity_method
    if payload.tested_on:
        product.tested_on = payload.tested_on
    db.commit()

    return Ok(
        detail=f"{product.sku} now points at lot {payload.lot}. "
               "Mirror this in data/products.json and rerun build.py so the "
               "static pages match."
    )


@router.get("/messages")
def list_messages(db: Session = Depends(get_db), handled: bool | None = None, limit: int = 100):
    query = db.query(ContactMessage)
    if handled is not None:
        query = query.filter(ContactMessage.handled == handled)
    rows = query.order_by(ContactMessage.created_at.desc()).limit(min(limit, 500)).all()
    return [
        {
            "id": m.id, "name": m.name, "email": m.email, "topic": m.topic,
            "order_ref": m.order_ref, "message": m.message,
            "handled": m.handled, "received": m.created_at,
        }
        for m in rows
    ]


@router.get("/integrations")
def integrations():
    """Which external connections are live and which are still placeholders."""
    return status_report()
