"""Catalog and COA endpoints. Read-only, cacheable, no auth."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Product
from ..schemas import CartIn, CartOut, CoaOut, ProductOut
from ..security import limiter
from ..services import PricingError, price_cart

router = APIRouter(tags=["catalog"])


@router.get("/products", response_model=list[ProductOut])
def list_products(
    response: Response,
    db: Session = Depends(get_db),
    category: str | None = Query(None, description="peptides | blends | solvents"),
    q: str | None = Query(None, max_length=80, description="Match name, SKU, compound or lot"),
    sort: str = Query("featured", pattern="^(featured|name|price_asc|price_desc)$"),
):
    query = db.query(Product)

    if category and category != "all":
        query = query.filter(Product.category == category)

    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(
            Product.name.ilike(pattern)
            | Product.sku.ilike(pattern)
            | Product.compound.ilike(pattern)
            | Product.lot.ilike(pattern)
        )

    order = {
        "featured": (Product.featured.desc(), Product.name.asc()),
        "name": (Product.name.asc(),),
        "price_asc": (Product.price_cents.asc(),),
        "price_desc": (Product.price_cents.desc(),),
    }[sort]

    # Catalog changes rarely; let the CDN carry the load.
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=3600"
    return query.order_by(*order).all()


@router.get("/products/{slug}", response_model=ProductOut)
def get_product(slug: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.slug == slug).first()
    if product is None:
        raise HTTPException(404, "No product with that slug.")
    return product


@router.get("/coas", response_model=list[CoaOut])
def list_coas(
    response: Response,
    db: Session = Depends(get_db),
    lot: str | None = Query(None, max_length=80, description="Lot code from the vial label"),
):
    """Public certificate index. Powers the COA library and lot lookup."""
    query = db.query(Product)
    if lot:
        query = query.filter(Product.lot.ilike(f"%{lot.strip()}%"))

    response.headers["Cache-Control"] = "public, max-age=300"
    return [
        CoaOut(
            sku=p.sku, name=p.name, compound=p.compound,
            lot="" if p.lot.startswith("PLACEHOLDER") else p.lot,
            purity=p.purity, purity_method=p.purity_method,
            tested_on=p.tested_on, coa_url=p.coa_url,
            published=bool(p.coa_url),
        )
        for p in query.order_by(Product.name.asc()).all()
    ]


@router.post("/cart/price", response_model=CartOut)
@limiter.limit("60/minute")
def price(request: Request, payload: CartIn, db: Session = Depends(get_db)):
    """Server-authoritative cart total.

    The storefront previews totals locally for responsiveness, then calls this
    before checkout so the figure on screen is one the server stands behind.
    """
    try:
        result = price_cart(db, payload.items, payload.promo_code)
    except PricingError as err:
        raise HTTPException(400, str(err)) from err

    result.pop("_cents", None)
    for line in result["items"]:
        line.pop("_product", None)
    return result
