"""Auth, hashing and rate limiting."""

import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter

from .config import settings

bearer = HTTPBearer(auto_error=False)


def client_ip(request: Request) -> str:
    """Behind Cloudflare or nginx the socket address is the proxy, so prefer
    the forwarded header and take the left-most hop."""
    for header in ("cf-connecting-ip", "x-forwarded-for", "x-real-ip"):
        value = request.headers.get(header)
        if value:
            return value.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# Explicit per-route limits only. A global default would also throttle static
# assets in single-process mode and lock out ordinary page loads.
limiter = Limiter(key_func=client_ip, default_limits=[], enabled=settings.rate_limit_enabled)


def hash_ip(ip: str) -> str:
    """Salted hash. We keep proof of consent without keeping the address."""
    return hashlib.sha256(f"{settings.ip_hash_salt}:{ip}".encode()).hexdigest()


def require_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> bool:
    """Constant-time comparison so a timing attack can't recover the token
    character by character."""
    if creds is None or not hmac.compare_digest(creds.credentials, settings.admin_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if settings.admin_token == "change-me-before-deploying":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_TOKEN is still the default. Set a real one in .env.",
        )
    return True


def order_reference() -> str:
    """Short, unambiguous, customer-quotable. No 0/O or 1/I confusion."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "VRC-" + "".join(secrets.choice(alphabet) for _ in range(6))
