"""Contact form intake."""

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ContactMessage
from ..schemas import ContactIn, Ok
from ..security import client_ip, hash_ip, limiter
from ..services import send_email

router = APIRouter(tags=["contact"])

ROUTE_TO = {
    "general": "hello@vrcsolutions.co",
    "order": "orders@vrcsolutions.co",
    "coa": "compliance@vrcsolutions.co",
    "compliance": "compliance@vrcsolutions.co",
    "privacy": "privacy@vrcsolutions.co",
}


@router.post("/contact", response_model=Ok)
@limiter.limit("5/minute;30/hour")
def submit(
    payload: ContactIn,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # Honeypot — accept silently so bots stop tuning their approach.
    if payload.website.strip():
        return Ok(detail="Message received.")

    message = ContactMessage(
        name=payload.name.strip(),
        email=str(payload.email).lower(),
        topic=payload.topic,
        order_ref=payload.order_ref.strip().upper(),
        message=payload.message.strip(),
        ip_hash=hash_ip(client_ip(request)),
    )
    db.add(message)
    db.commit()

    background.add_task(
        send_email,
        ROUTE_TO.get(payload.topic, "hello@vrcsolutions.co"),
        f"[{payload.topic}] {message.name}"
        + (f" — {message.order_ref}" if message.order_ref else ""),
        f"From: {message.name} <{message.email}>\n"
        f"Topic: {message.topic}\n"
        f"Order: {message.order_ref or '—'}\n\n{message.message}\n",
    )

    return Ok(detail="Message received. We reply within one business day.")
