"""
Production-ready rate limiting middleware for API security
"""

import time
import asyncio
from typing import Dict, Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse
import logging
import redis
from .config import settings

logger = logging.getLogger(__name__)

class RateLimiter:
    """Redis-based rate limiter for production use"""
    
    def __init__(self):
        self.redis_client = None
        self._connect_redis()
    
    def _connect_redis(self):
        """Connect to Redis. No in-memory fallback — shared state is required for multi-worker correctness."""
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                import redis
                self.redis_client = redis.Redis(
                    host=settings.REDIS_HOST if hasattr(settings, 'REDIS_HOST') else 'localhost',
                    port=settings.REDIS_PORT if hasattr(settings, 'REDIS_PORT') else 6379,
                    db=settings.REDIS_DB if hasattr(settings, 'REDIS_DB') else 0,
                    decode_responses=True,
                    socket_connect_timeout=10,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30,
                )
                self.redis_client.ping()
                logger.info("✅ Rate limiter connected to Redis")
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning("Redis connection attempt %d failed, retrying in %ds: %s",
                                   attempt + 1, retry_delay, e)
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error("Redis unavailable after %d attempts — rate limiter disabled: %s",
                                 max_retries, e)
                    self.redis_client = None
    
    # Lua script: atomically INCR the key and set its TTL on first creation.
    # KEYS[1] = the rate-limit key; ARGV[1] = window in seconds.
    # Returns the new count. Single-command atomicity avoids the INCR+EXPIRE
    # split that leaves a key with no TTL when the process crashes mid-pipeline.
    _LUA_INCR_EXPIRE = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""

    def _increment_key(self, key: str, expire: int) -> int:
        """Atomically increment counter via Lua. Returns 0 (allow) on Redis failure."""
        if not self.redis_client:
            return 0  # Redis unavailable — fail open rather than block all requests
        try:
            result = self.redis_client.eval(self._LUA_INCR_EXPIRE, 1, key, expire)
            return int(result)
        except Exception as e:
            logger.error("Redis rate-limit increment error: %s", e)
            return 0  # fail open
    
    def is_allowed(self, key: str, limit: int, window: int) -> tuple[bool, Dict]:
        """
        Check if request is allowed
        
        Args:
            key: Unique identifier (IP address or user ID)
            limit: Number of requests allowed
            window: Time window in seconds
            
        Returns:
            (allowed, info_dict)
        """
        current_time = int(time.time())
        window_start = current_time - (current_time % window)
        rate_key = f"rate_limit:{key}:{window_start}"

        current_count = self._increment_key(rate_key, window)
        
        # Calculate remaining requests and reset time
        remaining = max(0, limit - current_count)
        reset_time = window_start + window
        
        info = {
            "limit": limit,
            "remaining": remaining,
            "reset": reset_time,
            "retry_after": max(0, reset_time - current_time) if current_count >= limit else 0
        }
        
        return current_count <= limit, info

# Global rate limiter instance
rate_limiter = RateLimiter()

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for FastAPI"""

    # Endpoints that take a password / token / code get a much stricter limit than
    # the general API (brute-force protection). Routine authenticated calls under
    # /auth — /auth/me on every page load, /auth/sse-ticket, /auth/logout — use the
    # general limit: lumping them in let one office behind a single NAT IP lock
    # everyone out after 10 page loads in 5 minutes.
    _AUTH_PREFIXES = ("/api/auth/", "/api/v1/auth/")
    _AUTH_CREDENTIAL_WORDS = ("login", "token", "refresh", "mfa", "2fa", "otp", "password",
                              "register", "forgot", "reset", "verify", "signup")

    def __init__(self, app, calls: int = 100, period: int = 60,
                 auth_calls: int = None, auth_period: int = None):
        super().__init__(app)
        self.calls = calls  # Number of calls allowed (general API)
        self.period = period  # Time period in seconds (general API)
        # Auth-specific limits — wired from settings so RATE_LIMIT_AUTH_* is no
        # longer dead config. Defaults are conservative if not provided.
        self.auth_calls = auth_calls if auth_calls is not None else 10
        self.auth_period = auth_period if auth_period is not None else 300

    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiting"""

        client_id = self._get_client_id(request)

        # Apply the stricter auth limit to login/refresh/MFA endpoints.
        path = request.url.path
        if any(path.startswith(p) for p in self._AUTH_PREFIXES) and \
                any(w in path.lower() for w in self._AUTH_CREDENTIAL_WORDS):
            limit, window = self.auth_calls, self.auth_period
            scope = "auth"
        else:
            limit, window = self.calls, self.period
            scope = "api"

        allowed, info = rate_limiter.is_allowed(
            key=f"{scope}:{client_id}",
            limit=limit,
            window=window
        )

        # Reject BEFORE the handler runs so no DB/CPU work is done for limited requests.
        #
        # Return a JSONResponse rather than raising HTTPException: this is
        # BaseHTTPMiddleware, which sits OUTSIDE FastAPI's exception handlers, so a
        # raised HTTPException escapes as an unhandled error and the caller gets a
        # generic 500 "An unexpected error occurred" instead of 429. That turns a
        # few mistyped passwords into what looks like a server fault, and hides the
        # Retry-After the client needs.
        if not allowed:
            logger.warning(f"Rate limit exceeded for {client_id} on {scope}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Try again in {info['retry_after']} seconds.",
                    "retry_after": info["retry_after"],
                    "limit": info["limit"],
                    "period": window,
                },
                headers={
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": str(info["remaining"]),
                    "X-RateLimit-Reset": str(info["reset"]),
                    "X-RateLimit-RetryAfter": str(info["retry_after"]),
                    "Retry-After": str(info["retry_after"])
                }
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])
        response.headers["X-RateLimit-RetryAfter"] = str(info["retry_after"])
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """Get a spoof-resistant client identifier.

        IMPORTANT: this middleware runs OUTSIDE RBACMiddleware, so request.state.user
        is not yet populated — keying must be IP-based here. We therefore derive the IP
        from headers our OWN reverse proxy sets, NOT from client-controllable ones:

          1. X-Real-IP — nginx sets this to $remote_addr (the true TCP peer) and
             overwrites any client value, so it cannot be spoofed through nginx.
          2. The RIGHTMOST entry of X-Forwarded-For — nginx APPENDS $remote_addr to
             the right via $proxy_add_x_forwarded_for, so the last token is the real
             peer. (Taking the LEFTMOST token, as before, trusted client input and let
             an attacker mint unlimited buckets by rotating the header.)
          3. request.client.host as a last resort.
        """
        # Try to get user ID from authenticated request (rarely set at this layer)
        if hasattr(request.state, 'user') and request.state.user:
            return f"user:{request.state.user.id}"

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            ip = real_ip.strip()
        else:
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                # Rightmost token = appended by our proxy = the genuine peer
                ip = forwarded_for.split(",")[-1].strip()
            else:
                ip = request.client.host if request.client else "unknown"

        return f"ip:{ip}"

def add_rate_limit_middleware(app):
    """Add rate limiting middleware to FastAPI app.

    General API limit and the stricter auth limit are both sourced from settings
    so RATE_LIMIT_AUTH_REQUESTS / RATE_LIMIT_AUTH_WINDOW are actually enforced.
    """
    # General limit stays at the proven 1000/min/IP — dropping to the low config
    # default would break offices where many users share one NAT'd IP. The strict
    # auth limit is sourced from settings (defense-in-depth behind nginx auth_limit).
    api_calls = 1000
    api_period = 60
    auth_calls = getattr(settings, "RATE_LIMIT_AUTH_REQUESTS", 10)
    auth_period = getattr(settings, "RATE_LIMIT_AUTH_WINDOW", 300)

    app.add_middleware(
        RateLimitMiddleware,
        calls=api_calls,
        period=api_period,
        auth_calls=auth_calls,
        auth_period=auth_period,
    )

    logger.info(
        "✅ Rate limiting middleware added (api=%s/%ss, auth=%s/%ss)",
        api_calls, api_period, auth_calls, auth_period,
    )
    return app
