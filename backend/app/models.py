"""ORM models.

Money is stored in cents as integers. Floats cannot represent 0.1 exactly, and
accumulated rounding error in a cart total is the kind of bug that surfaces as
an angry email six months later.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    compound: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40), index=True)

    price_cents: Mapped[int] = mapped_column(Integer)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    featured: Mapped[bool] = mapped_column(Boolean, default=False)

    mass: Mapped[str] = mapped_column(String(80), default="")
    molecular_weight: Mapped[str] = mapped_column(String(80), default="")
    purity: Mapped[str] = mapped_column(String(32), default="")
    purity_method: Mapped[str] = mapped_column(String(40), default="")
    lot: Mapped[str] = mapped_column(String(80), default="", index=True)
    storage: Mapped[str] = mapped_column(String(200), default="")
    tested_on: Mapped[str] = mapped_column(String(20), default="")

    coa_url: Mapped[str] = mapped_column(Text, default="")
    coa_type: Mapped[str] = mapped_column(String(20), default="missing")
    image: Mapped[str] = mapped_column(Text, default="")
    image_alt: Mapped[str] = mapped_column(Text, default="")

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    @property
    def price(self) -> float:
        return self.price_cents / 100


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(20), unique=True, index=True)

    email: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(160))
    address1: Mapped[str] = mapped_column(String(200))
    address2: Mapped[str] = mapped_column(String(200), default="")
    city: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(2))
    postal_code: Mapped[str] = mapped_column(String(12))
    country: Mapped[str] = mapped_column(String(2), default="US")

    payment_method: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="awaiting_payment", index=True)

    subtotal_cents: Mapped[int] = mapped_column(Integer, default=0)
    discount_cents: Mapped[int] = mapped_column(Integer, default=0)
    shipping_cents: Mapped[int] = mapped_column(Integer, default=0)
    total_cents: Mapped[int] = mapped_column(Integer, default=0)
    promo_code: Mapped[str] = mapped_column(String(40), default="")

    tracking_number: Mapped[str] = mapped_column(String(80), default="")
    internal_note: Mapped[str] = mapped_column(Text, default="")

    # Evidence that the buyer affirmed the RUO terms for THIS order. Keep it.
    ruo_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    ruo_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ip_hash: Mapped[str] = mapped_column(String(64), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


class OrderItem(Base):
    """Prices and lot numbers are copied in at order time.

    If a price changes or a lot rotates next month, this record still shows what
    the customer actually bought and which batch it came from. That matters for
    both refunds and compliance.
    """

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)

    sku: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(160))
    unit_price_cents: Mapped[int] = mapped_column(Integer)
    qty: Mapped[int] = mapped_column(Integer)
    lot_at_purchase: Mapped[str] = mapped_column(String(80), default="")

    order: Mapped[Order] = relationship(back_populates="items")


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(255), index=True)
    topic: Mapped[str] = mapped_column(String(40), default="general")
    order_ref: Mapped[str] = mapped_column(String(20), default="")
    message: Mapped[str] = mapped_column(Text)
    handled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    ip_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class RuoAcknowledgment(Base):
    """Audit trail for the age / research-use gate.

    Stores a salted hash of the IP rather than the address itself: enough to
    demonstrate a pattern of consent, not enough to identify a visitor.
    """

    __tablename__ = "ruo_acknowledgments"

    id: Mapped[int] = mapped_column(primary_key=True)
    ip_hash: Mapped[str] = mapped_column(String(64), index=True)
    user_agent: Mapped[str] = mapped_column(Text, default="")
    path: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


Index("ix_products_category_featured", Product.category, Product.featured)
