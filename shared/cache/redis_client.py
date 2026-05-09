"""Redis-backed JWT blocklist + per-tenant rate limit middleware.

Used by every service that decodes JWTs. Fail-open if Redis is unreachable so
a Redis outage doesn't take the whole API down — the trade-off is that during
that window logout-blocked tokens may still be honored. Acceptable for this
learning project; revisit if used in production.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import redis
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

BLOCKLIST_KEY_PREFIX = "jwt:blocklist:"
RATE_LIMIT_KEY_PREFIX = "ratelimit:"

_logger = logging.getLogger(__name__)
_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Lazy singleton. decode_responses=True so we get str, not bytes."""
    global _client
    if _client is None:
        url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        _client = redis.Redis.from_url(url, decode_responses=True)
    return _client


# -------- JWT blocklist --------

def blocklist_jti(jti: str, ttl_seconds: int) -> None:
    """Mark a JWT id as revoked. TTL should match the token's remaining life."""
    if ttl_seconds <= 0:
        return
    try:
        get_redis().setex(BLOCKLIST_KEY_PREFIX + jti, ttl_seconds, "1")
    except redis.RedisError:
        _logger.exception("blocklist_jti: redis unavailable")


def is_jti_blocked(jti: str) -> bool:
    try:
        return bool(get_redis().exists(BLOCKLIST_KEY_PREFIX + jti))
    except redis.RedisError:
        _logger.exception("is_jti_blocked: redis unavailable, failing open")
        return False


# -------- Per-tenant rate limit --------

def _peek_jwt(token: str) -> dict[str, Any] | None:
    """Decode without raising. Returns None on any failure (the route's
    dependency will reject the request properly)."""
    secret = os.getenv("JWT_SECRET", "")
    algo = os.getenv("JWT_ALGORITHM", "HS256")
    if not secret:
        return None
    try:
        return jwt.decode(token, secret, algorithms=[algo])
    except JWTError:
        return None


def _rate_limit_key(request: Request) -> str:
    """Prefer tenant_id, then user_id, then client IP."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        payload = _peek_jwt(auth.split(" ", 1)[1].strip())
        if payload:
            tid = payload.get("tenant_id")
            if tid:
                return f"tenant:{tid}"
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
    ip = request.client.host if request.client else "unknown"
    return f"ip:{ip}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window per-minute counter. Exempts /health probes."""

    def __init__(self, app: Any, limit_per_minute: int | None = None) -> None:
        super().__init__(app)
        self.limit = limit_per_minute or int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if request.url.path.endswith("/health"):
            return await call_next(request)

        bucket = int(time.time() // 60)
        key = f"{RATE_LIMIT_KEY_PREFIX}{_rate_limit_key(request)}:{bucket}"
        try:
            r = get_redis()
            count = int(r.incr(key))  # type: ignore[arg-type]
            if count == 1:
                r.expire(key, 60)
        except redis.RedisError:
            _logger.exception("rate limit: redis unavailable, failing open")
            return await call_next(request)

        if count > self.limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": "60"},
            )
        return await call_next(request)
