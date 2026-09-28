"""HTTP middleware: request logging, timing header, rate limiting.

The rate limiter uses ONE shared Redis connection with a circuit breaker:
when Redis is absent (local no-Docker runs) it fails over to an in-memory
counter instead of paying a connection timeout on every request.
"""
import logging
import time
from collections import defaultdict

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("app.http")

RATE_LIMIT_REQUESTS = 120
RATE_LIMIT_WINDOW_SECONDS = 60
REDIS_RETRY_SECONDS = 30.0

# Tighter budgets for expensive/sensitive endpoint groups. Applied on top of
# the general per-IP limit; both must pass. Never blocks normal use.
GROUP_LIMITS: list[tuple[str, str, int]] = [
    ("/api/v1/auth/register", "register", 10),
    ("/api/v1/auth/login", "login", 20),
    ("/api/v1/auth/forgot-password", "pwreset", 5),
    ("/api/v1/disease/analyze", "scan", 20),
    ("/api/v1/chat/messages", "chat", 40),
    ("/api/v1/chat/messages/stream", "chat", 40),
    ("/api/v1/crops/recommend", "ai", 30),
    ("/api/v1/profit/predict", "ai", 30),
    ("/api/v1/market/analyze", "ai", 30),
]

# Per-IP group counters: (group, ip, window) -> count
_group_windows: dict[tuple[str, str, int], int] = {}


def _allow_group(key: str, max_requests: int) -> bool:
    """Group fixed-window check; Redis first, memory fallback."""
    window = int(time.time() // RATE_LIMIT_WINDOW_SECONDS)
    client = _get_redis()
    if client is not None:
        try:
            redis_key = f"rlg:{key}:{window}"
            count = client.incr(redis_key)
            if count == 1:
                client.expire(redis_key, RATE_LIMIT_WINDOW_SECONDS)
            return count <= max_requests
        except Exception:
            pass
    entry = _group_windows.get(key)
    if not entry or entry[0] != window:
        if len(_group_windows) > 4096:
            for k in [k for k, (w, _) in _group_windows.items() if w != window][:2048]:
                _group_windows.pop(k, None)
        _group_windows[key] = (window, 1)
        return True
    _group_windows[key] = (window, entry[1] + 1)
    return entry[1] + 1 <= max_requests

_shared_redis = None
_redis_dead_until = 0.0

# In-memory fallback: key -> (window_start, count)
_memory_windows: dict[str, tuple[int, int]] = {}


def _get_redis():
    global _shared_redis, _redis_dead_until
    now = time.monotonic()
    if _shared_redis is not None:
        return _shared_redis
    if now < _redis_dead_until:
        return None
    try:
        import redis

        from app.core.config import settings

        client = redis.Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=0.25,
            socket_timeout=0.25,
            decode_responses=True,
        )
        client.ping()
        _shared_redis = client
        return client
    except Exception:
        _redis_dead_until = now + REDIS_RETRY_SECONDS
        return None


def _allow(key: str) -> bool:
    """Fixed-window check; Redis first, memory fallback. Never blocks >50ms."""
    window = int(time.time() // RATE_LIMIT_WINDOW_SECONDS)
    client = _get_redis()
    if client is not None:
        try:
            redis_key = f"rl:{key}:{window}"
            count = client.incr(redis_key)
            if count == 1:
                client.expire(redis_key, RATE_LIMIT_WINDOW_SECONDS)
            return count <= RATE_LIMIT_REQUESTS
        except Exception:
            pass
    # Memory fallback
    entry = _memory_windows.get(key)
    if not entry or entry[0] != window:
        _memory_windows[key] = (window, 1)
        # opportunistic cleanup
        if len(_memory_windows) > 2048:
            for k in [k for k, (w, _) in _memory_windows.items() if w != window][:1024]:
                _memory_windows.pop(k, None)
        return True
    _memory_windows[key] = (window, entry[1] + 1)
    return entry[1] + 1 <= RATE_LIMIT_REQUESTS


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
        if request.url.path not in ("/health", "/api/v1/health"):
            logger.info(
                "%s %s -> %s (%.1f ms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP fixed-window limiter: Redis when present, memory otherwise.

    Two layers: a general 120 req/min per-IP budget plus tighter group
    budgets on auth and AI endpoints (see GROUP_LIMITS).
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health", "/api/v1/health"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        # Group budgets first (stricter limit for sensitive endpoints)
        for prefix, group, group_max in GROUP_LIMITS:
            if request.url.path.startswith(prefix):
                if not _allow_group((group, client_ip), group_max):
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)},
                        content={"detail": "Too many requests. Please wait a minute and try again."},
                    )
                break

        if not _allow(client_ip):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)},
                content={"detail": "Too many requests. Please wait a minute and try again."},
            )
        return await call_next(request)


def get_middlewares() -> list:
    """Middleware classes (not instances) for app.add_middleware()."""
    return [RequestLoggingMiddleware, RateLimitMiddleware]
