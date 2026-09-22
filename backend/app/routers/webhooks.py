"""Inbound webhooks from payment and shipping providers (placeholders)."""

from fastapi import APIRouter, HTTPException, Request

from ..integrations import WEBHOOKS, NotConfigured
from ..security import limiter

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/{provider}", status_code=202)
@limiter.limit("120/minute")
async def receive(request: Request, provider: str):
    handler = WEBHOOKS.get(provider)
    if handler is None:
        raise HTTPException(404, "Unknown webhook provider")
    try:
        handler(request.headers, await request.body())
    except NotConfigured as exc:
        raise HTTPException(501, str(exc)) from exc
    return {"ok": True}
