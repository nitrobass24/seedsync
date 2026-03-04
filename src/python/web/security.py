# Copyright 2017, Inderpreet Singh, All rights reserved.

import secrets
import time
import threading
from collections import defaultdict
from urllib.parse import urlparse

import bottle


# ---------------------------------------------------------------------------
# Security Response Headers
# ---------------------------------------------------------------------------

def install_security_headers(app: bottle.Bottle):
    """
    Add security response headers to every response via an after_request hook.
    """
    @app.hook("after_request")
    def _add_security_headers():
        bottle.response.headers["X-Content-Type-Options"] = "nosniff"
        bottle.response.headers["X-Frame-Options"] = "DENY"
        bottle.response.headers["X-XSS-Protection"] = "1; mode=block"
        bottle.response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        bottle.response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "font-src 'self'"
        )


# ---------------------------------------------------------------------------
# CSRF Protection
# ---------------------------------------------------------------------------

_CSRF_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_CSRF_LOCALHOST = frozenset({"localhost", "127.0.0.1", "::1"})


def _origin_host_port(header_value):
    """Extract host:port from an Origin or Referer header value.
    Returns 'host:port' if port is present, otherwise 'host'."""
    if not header_value:
        return None
    try:
        parsed = urlparse(header_value)
        host = parsed.hostname
        if not host:
            return None
        port = parsed.port
        return "{}:{}".format(host, port) if port else host
    except Exception:
        return None


def install_csrf_protection(app: bottle.Bottle):
    """
    Validate Origin/Referer on state-changing requests (POST/PUT/DELETE/PATCH).
    Requests from localhost/127.0.0.1/::1 are exempt.
    """
    @app.hook("before_request")
    def _csrf_check():
        if bottle.request.method in _CSRF_SAFE_METHODS:
            return

        # Exempt genuine loopback connections (server-observed client IP, not client-controlled headers)
        remote_addr = bottle.request.environ.get("REMOTE_ADDR", "")
        if remote_addr in _CSRF_LOCALHOST:
            return

        # Check Origin first, then Referer
        origin = bottle.request.get_header("Origin")
        referer = bottle.request.get_header("Referer")

        origin_hp = _origin_host_port(origin) if origin else _origin_host_port(referer)

        if origin_hp is None:
            raise bottle.HTTPError(403, "CSRF validation failed: missing Origin/Referer")

        # Compare origin host:port against the Host header (exact match including port)
        request_host = bottle.request.get_header("Host", "")

        if origin_hp != request_host:
            raise bottle.HTTPError(403, "CSRF validation failed: origin mismatch")


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------

class _RateLimiter:
    """Per-IP sliding-window rate limiter (in-memory)."""

    def __init__(self, max_requests: int = 120, window_seconds: int = 60):
        self._max = max_requests
        self._window = window_seconds
        self._hits = defaultdict(list)   # ip -> [timestamps]
        self._lock = threading.Lock()

    def is_allowed(self, ip: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window

        with self._lock:
            timestamps = self._hits[ip]
            # Prune expired entries
            valid = [t for t in timestamps if t > cutoff]
            if not valid:
                # Remove empty key to prevent unbounded memory growth
                del self._hits[ip]
                self._hits[ip] = [now]
                return True
            if len(valid) >= self._max:
                self._hits[ip] = valid
                return False
            valid.append(now)
            self._hits[ip] = valid
            return True

    def retry_after(self, ip: str) -> int:
        """Seconds until the oldest request in the window expires."""
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            timestamps = self._hits[ip]
            valid = [t for t in timestamps if t > cutoff]
            if not valid:
                return 0
            return max(1, int(valid[0] - cutoff + 1))


_SSE_STREAM_PATH = "/server/stream"


def install_rate_limiting(app: bottle.Bottle, trust_x_forwarded_for: bool = False):
    """
    Per-IP sliding window rate limiter.  Returns 429 with Retry-After when
    the limit is exceeded.  The SSE stream endpoint is exempt.

    :param trust_x_forwarded_for: Only set True when deployed behind a trusted reverse proxy.
    """
    limiter = _RateLimiter()

    @app.hook("before_request")
    def _rate_limit():
        if bottle.request.path == _SSE_STREAM_PATH:
            return

        # Only trust X-Forwarded-For when explicitly enabled (behind trusted reverse proxy)
        ip = None
        if trust_x_forwarded_for:
            forwarded = bottle.request.get_header("X-Forwarded-For")
            if forwarded:
                ip = forwarded.split(",")[0].strip()
        if not ip:
            ip = bottle.request.environ.get("REMOTE_ADDR", "127.0.0.1")

        if not limiter.is_allowed(ip):
            retry = limiter.retry_after(ip)
            resp = bottle.HTTPError(429, "Rate limit exceeded")
            resp.headers["Retry-After"] = str(retry)
            raise resp


# ---------------------------------------------------------------------------
# API Key Authentication
# ---------------------------------------------------------------------------

_API_KEY_EXEMPT_PATHS = frozenset({"/server/config/get"})


def install_api_key_auth(app: bottle.Bottle, get_api_key):
    """
    Require X-Api-Key header on /server/* routes when an API key is configured.
    The SSE stream endpoint also accepts ?api_key= query parameter.
    The config GET endpoint is exempt so the frontend can bootstrap.

    :param app: Bottle application
    :param get_api_key: callable returning the current API key string
    """
    @app.hook("before_request")
    def _api_key_check():
        configured_key = get_api_key()
        if not configured_key:
            return  # auth disabled

        path = bottle.request.path
        if not path.startswith("/server/"):
            return  # only protect API routes

        if path in _API_KEY_EXEMPT_PATHS:
            return  # exempt for frontend bootstrapping

        # Check header first
        provided = bottle.request.get_header("X-Api-Key")

        # SSE stream also accepts query parameter
        if not provided and path == _SSE_STREAM_PATH:
            provided = bottle.request.params.get("api_key")

        if not provided:
            raise bottle.HTTPError(401, "API key required")
        if not secrets.compare_digest(provided, configured_key):
            raise bottle.HTTPError(401, "Invalid API key")


# ---------------------------------------------------------------------------
# Convenience installer
# ---------------------------------------------------------------------------

def install_security_middleware(app: bottle.Bottle, get_api_key=None,
                               trust_x_forwarded_for: bool = False):
    """Install all security middleware on the given Bottle app.

    :param trust_x_forwarded_for: Pass True only when behind a trusted reverse proxy.
    """
    install_security_headers(app)
    install_csrf_protection(app)
    install_rate_limiting(app, trust_x_forwarded_for=trust_x_forwarded_for)
    if get_api_key is not None:
        install_api_key_auth(app, get_api_key)
