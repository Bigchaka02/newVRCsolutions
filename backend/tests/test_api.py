"""API tests. Run from backend/:  python -m pytest -q

These pin down the rules most likely to cost money or compliance standing if
they regress: server-side pricing, the RUO confirmation, US-only shipping,
admin auth and rate limiting.
"""

def price(client, items, promo=None):
    return client.post("/api/cart/price", json={"items": items, "promo_code": promo})


# ---------- catalog ------------------------------------------------------

def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_catalog_filters_and_sorts(client):
    rows = client.get("/api/products?category=solvents&sort=price_asc").json()
    assert rows and all(r["category"] == "solvents" for r in rows)
    prices = [r["price"] for r in rows]
    assert prices == sorted(prices)


def test_search_matches_lot_numbers(client):
    rows = client.get("/api/products?q=AS-BPC10").json()
    assert [r["sku"] for r in rows] == ["BPC10"]


def test_unknown_slug_is_404(client):
    assert client.get("/api/products/not-a-product").status_code == 404


def test_coa_index_hides_placeholder_lots(client):
    rows = {r["sku"]: r for r in client.get("/api/coas").json()}
    assert rows["BPC10"]["published"] is True
    assert rows["TB10"]["published"] is False
    assert rows["TB10"]["lot"] == ""  # never leak "PLACEHOLDER-..." to the public


# ---------- pricing ------------------------------------------------------

def test_shipping_charged_under_threshold(client):
    r = price(client, [{"sku": "BPC10", "qty": 1}]).json()
    assert (r["subtotal"], r["shipping"], r["total"]) == (39.99, 9.95, 49.94)


def test_free_shipping_over_threshold(client):
    r = price(client, [{"sku": "RT20", "qty": 1}]).json()
    assert r["shipping"] == 0 and r["total"] == 112.99


def test_promo_cannot_jump_free_shipping_line(client):
    # 112.99 - 15% = 96.04, which is under 105, so shipping applies.
    r = price(client, [{"sku": "RT20", "qty": 1}], "first15").json()
    assert r["promo_applied"] is True
    assert r["discount"] == 16.95
    assert r["shipping"] == 9.95
    assert r["total"] == 105.99


def test_unknown_promo_is_reported_not_applied(client):
    r = price(client, [{"sku": "BPC10", "qty": 1}], "NOPE").json()
    assert r["promo_applied"] is False and r["discount"] == 0
    assert any("NOPE" in n for n in r["notices"])


def test_client_cannot_set_prices(client):
    r = price(client, [{"sku": "BPC10", "qty": 1, "price": 0.01}]).json()
    assert r["subtotal"] == 39.99


def test_unknown_sku_rejected(client):
    r = price(client, [{"sku": "FAKE", "qty": 1}])
    assert r.status_code == 400 and "FAKE" in r.json()["detail"]


# ---------- orders -------------------------------------------------------

def test_order_lifecycle(client, order_payload):
    r = client.post("/api/orders", json=order_payload)
    assert r.status_code == 201
    order = r.json()
    ref = order["reference"]
    assert ref.startswith("VRC-")
    assert order["total"] == 90.67  # 94.97 - 14.25 + 9.95
    assert order["payment_instructions"]["reference"] == ref

    found = client.get(f"/api/orders/{ref}?email=LAB@example.com").json()
    assert found["status"] == "awaiting_payment"
    # Lot snapshot: the order remembers which batch shipped.
    assert {"sku": "BPC10", "lot": "AS-BPC10-0426"}.items() <= found["items"][0].items()

    assert client.get(f"/api/orders/{ref}?email=someone@else.com").status_code == 404


def test_order_requires_ruo_confirmation(client, order_payload):
    r = client.post("/api/orders", json={**order_payload, "ruo_confirmed": False})
    assert r.status_code == 422
    assert "research use only" in r.json()["detail"][0]["msg"]


def test_us_only(client, order_payload):
    assert client.post("/api/orders", json={**order_payload, "state": "ZZ"}).status_code == 422


def test_bad_zip_rejected(client, order_payload):
    assert client.post("/api/orders", json={**order_payload, "postal_code": "ABCDE"}).status_code == 422


def test_empty_cart_rejected(client, order_payload):
    assert client.post("/api/orders", json={**order_payload, "items": []}).status_code == 422


def test_honeypot_creates_nothing(client, admin, order_payload):
    before = len(client.get("/api/admin/orders", headers=admin).json())
    r = client.post("/api/orders", json={**order_payload, "website": "http://spam"})
    assert r.status_code == 201  # the bot believes it worked
    assert len(client.get("/api/admin/orders", headers=admin).json()) == before


# ---------- contact & compliance ----------------------------------------

def test_contact(client):
    r = client.post("/api/contact", json={
        "name": "Jo", "email": "jo@example.com", "topic": "coa",
        "message": "Please send the certificate for lot AS-BPC10-0426.",
    })
    assert r.status_code == 200 and r.json()["ok"] is True


def test_contact_rejects_short_message(client):
    r = client.post("/api/contact", json={"name": "Jo", "email": "jo@example.com", "message": "hi"})
    assert r.status_code == 422


def test_ruo_ack(client):
    assert client.post("/api/compliance/ruo-ack", json={"path": "/shop/"}).json()["ok"] is True


# ---------- admin --------------------------------------------------------

def test_admin_requires_token(client):
    assert client.get("/api/admin/orders").status_code == 401
    assert client.get("/api/admin/orders", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_admin_ships_order(client, admin, order_payload):
    ref = client.post("/api/orders", json=order_payload).json()["reference"]
    r = client.patch(f"/api/admin/orders/{ref}", headers=admin,
                     json={"status": "shipped", "tracking_number": "9400100000000000000000"})
    assert r.status_code == 200
    found = client.get(f"/api/orders/{ref}?email=lab@example.com").json()
    assert found["status"] == "shipped" and found["tracking_number"].startswith("9400")


def test_admin_rejects_unknown_status(client, admin, order_payload):
    ref = client.post("/api/orders", json=order_payload).json()["reference"]
    r = client.patch(f"/api/admin/orders/{ref}", headers=admin, json={"status": "teleported"})
    assert r.status_code == 400


def test_admin_rotates_coa(client, admin):
    r = client.patch("/api/admin/products/MTC10/coa", headers=admin, json={
        "lot": "MTC10-0922", "coa_url": "https://example.org/coa/mtc10", "purity": "99.3%",
    })
    assert r.status_code == 200
    row = next(x for x in client.get("/api/coas").json() if x["sku"] == "MTC10")
    assert row["published"] is True and row["lot"] == "MTC10-0922"


# ---------- hardening ----------------------------------------------------

def test_contact_is_rate_limited(client):
    body = {"name": "Jo", "email": "jo@example.com", "message": "A perfectly valid message."}
    codes = [client.post("/api/contact", json=body).status_code for _ in range(6)]
    assert codes[:5] == [200] * 5
    assert codes[5] == 429


def test_security_headers(client):
    h = client.get("/api/health").headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
