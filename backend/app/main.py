"""VRC Solutions API — FastAPI application entry point.

    uvicorn app.main:app --reload

Interactive docs at /api/docs while APP_ENV is not production.
"""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import settings
from .db import Base, engine
from .routers import admin, catalog, compliance, contact, orders, webhooks
from .security import limiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("vrc")

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="VRC Solutions API",
    version="1.0.0",
    description=(
        "Catalog, COA index, cart pricing and orders for vrcsolutions.co. "
        "All products are sold for laboratory research use only."
    ),
    docs_url=None if settings.is_production else "/api/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/api/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Baseline security headers on every API response.

    The storefront's Content-Security-Policy lives in public/_headers (written
    by build.py) because in the recommended setup the CDN serves the pages,
    not this process.
    """
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if settings.is_production:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    """Log the detail, tell the customer something useful, leak nothing."""
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Something went wrong on our end. "
                      "Email support@vrcsolutions.co if this keeps happening."
        },
    )


for router in (catalog.router, orders.router, contact.router, compliance.router, admin.router, webhooks.router):
    app.include_router(router, prefix="/api")


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok", "env": settings.app_env}


# --------------------------------------------------------------------------
# Optional: serve the static site from this same process.
# --------------------------------------------------------------------------

def _load_redirects(static_root: Path) -> dict[str, str]:
    """Reuse the _redirects file build.py writes for the CDN, so legacy
    WordPress URLs behave identically in both deployment modes."""
    table: dict[str, str] = {}
    rules = static_root / "_redirects"
    if rules.exists():
        for line in rules.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) >= 2 and not line.lstrip().startswith("#"):
                table[parts[0]] = parts[1]
    return table


if settings.serve_static:
    static_root = (Path(__file__).resolve().parent.parent / settings.static_dir).resolve()
    if not (static_root / "index.html").exists():
        log.warning("SERVE_STATIC is on but %s has no index.html. Run build.py first.", static_root)
    else:
        redirects = _load_redirects(static_root)

        @app.middleware("http")
        async def legacy_redirects(request: Request, call_next):
            target = redirects.get(request.url.path)
            if target:
                return RedirectResponse(target, status_code=301)
            return await call_next(request)

        # Mounted last, so every /api route above takes precedence.
        app.mount("/", StaticFiles(directory=static_root, html=True), name="site")
        log.info("Serving static site from %s with %d legacy redirects", static_root, len(redirects))
