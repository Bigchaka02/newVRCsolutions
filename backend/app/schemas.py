"""Request and response shapes. Pydantic rejects malformed input at the edge,
so handlers only ever see data that has already been validated."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# States we ship to. Anything else is rejected before an order is created.
US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC",
}


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku: str
    slug: str
    name: str
    compound: str
    category: str
    price: float
    in_stock: bool
    featured: bool
    mass: str
    molecular_weight: str
    purity: str
    purity_method: str
    lot: str
    storage: str
    tested_on: str
    coa_url: str
    coa_type: str
    image: str
    image_alt: str


class CoaOut(BaseModel):
    """Deliberately narrower than ProductOut — the COA endpoint is about
    verification, not merchandising, so it returns no prices."""

    sku: str
    name: str
    compound: str
    lot: str
    purity: str
    purity_method: str
    tested_on: str
    coa_url: str
    published: bool


class CartLineIn(BaseModel):
    sku: str = Field(min_length=1, max_length=32)
    qty: int = Field(ge=1, le=99)


class CartIn(BaseModel):
    items: list[CartLineIn] = Field(min_length=1, max_length=40)
    promo_code: str | None = Field(default=None, max_length=40)


class PricedLine(BaseModel):
    sku: str
    name: str
    unit_price: float
    qty: int
    line_total: float


class CartOut(BaseModel):
    items: list[PricedLine]
    subtotal: float
    discount: float
    shipping: float
    total: float
    promo_applied: bool
    free_shipping_remaining: float
    notices: list[str] = []


class OrderIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=160)
    address1: str = Field(min_length=3, max_length=200)
    address2: str = Field(default="", max_length=200)
    city: str = Field(min_length=2, max_length=120)
    state: str = Field(min_length=2, max_length=2)
    postal_code: str = Field(min_length=5, max_length=10)
    payment_method: Literal["venmo", "cashapp", "crypto", "card"]
    ruo_confirmed: bool
    items: list[CartLineIn] = Field(min_length=1, max_length=40)
    promo_code: str | None = Field(default=None, max_length=40)
    website: str = ""  # honeypot

    @field_validator("state")
    @classmethod
    def valid_state(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in US_STATES:
            raise ValueError("We ship within the United States only.")
        return v

    @field_validator("ruo_confirmed")
    @classmethod
    def must_confirm(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "You must confirm you are 21 or over and purchasing for "
                "laboratory research use only."
            )
        return v

    @field_validator("postal_code")
    @classmethod
    def valid_zip(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned.replace("-", "").isdigit():
            raise ValueError("Enter a valid US ZIP code.")
        return cleaned


class OrderOut(BaseModel):
    reference: str
    status: str
    email: str
    subtotal: float
    discount: float
    shipping: float
    total: float
    payment_instructions: dict
    created_at: datetime


class ContactIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    topic: Literal["general", "order", "coa", "compliance", "privacy"] = "general"
    order_ref: str = Field(default="", max_length=20)
    message: str = Field(min_length=10, max_length=4000)
    website: str = ""  # honeypot


class RuoAckIn(BaseModel):
    path: str = Field(default="/", max_length=255)
    at: str | None = None


class Ok(BaseModel):
    ok: bool = True
    detail: str = ""
