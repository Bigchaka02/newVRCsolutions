"""Test setup. Environment must be set before the app is imported, because
settings are read once at import time."""

import os
import sys
import tempfile
from pathlib import Path

DB = Path(tempfile.gettempdir()) / "vrc_test.db"
DB.unlink(missing_ok=True)

os.environ.update({
    "DATABASE_URL": f"sqlite:///{DB}",
    "ADMIN_TOKEN": "test-admin-token-1234567890",
    "IP_HASH_SALT": "test-salt",
    "APP_ENV": "test",
    "SMTP_HOST": "",
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import seed  # noqa: E402
from app.main import app  # noqa: E402
from app.security import limiter  # noqa: E402

seed.run()

ADMIN = {"Authorization": "Bearer test-admin-token-1234567890"}


@pytest.fixture(autouse=True)
def _reset_limits():
    limiter.reset()
    yield


@pytest.fixture
def admin():
    return ADMIN


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def order_payload():
    return {
        "email": "lab@example.com", "name": "A Researcher", "address1": "1 Lab St",
        "city": "Louisville", "state": "ky", "postal_code": "40241",
        "payment_method": "venmo", "ruo_confirmed": True,
        "items": [{"sku": "BPC10", "qty": 2}, {"sku": "BW10", "qty": 1}],
        "promo_code": "FIRST15",
    }
