"""Load data/products.json into the database.

Idempotent — run it as often as you like. Products are matched on SKU and
updated in place, so rotating a lot is: edit the JSON, run this, rerun
build.py.

    python3 -m app.seed
"""

import json
from pathlib import Path

from .db import Base, SessionLocal, engine
from .models import Product

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "products.json"


def run() -> None:
    Base.metadata.create_all(bind=engine)
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    db = SessionLocal()
    created = updated = 0

    try:
        for item in payload["products"]:
            fields = {
                "slug": item["slug"],
                "name": item["name"],
                "compound": item["compound"],
                "category": item["category"],
                # Round through cents once, here, so no float ever reaches the DB.
                "price_cents": round(float(item["price"]) * 100),
                "in_stock": bool(item.get("stock", True)),
                "featured": bool(item.get("featured", False)),
                "mass": item.get("mass", ""),
                "molecular_weight": item.get("molecular_weight", ""),
                "purity": item.get("purity", ""),
                "purity_method": item.get("purity_method", ""),
                "lot": item.get("lot", ""),
                "storage": item.get("storage", ""),
                "tested_on": item.get("tested", ""),
                "coa_url": item.get("coa_url", ""),
                "coa_type": item.get("coa_type", "missing"),
                "image": item.get("image", ""),
                "image_alt": item.get("image_alt", ""),
            }

            existing = db.query(Product).filter(Product.sku == item["sku"]).first()
            if existing:
                for key, value in fields.items():
                    setattr(existing, key, value)
                updated += 1
            else:
                db.add(Product(sku=item["sku"], **fields))
                created += 1

        db.commit()
        total = db.query(Product).count()
        missing = db.query(Product).filter(Product.coa_url == "").count()

        print(f"Seeded: {created} created, {updated} updated, {total} products total.")
        if missing:
            print(f"WARNING: {missing} products have no COA URL. "
                  "They show a 'Pending' badge rather than a broken link.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
