# Copyright 2017, Inderpreet Singh, All rights reserved.

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


def _origin_host(header_value):
    """Extract the hostname from an Origin or Referer header value."""
    if not header_value:
        return None
    try:
        parsed = urlparse(header_value)
        return parsed.hostname
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

        # Exempt requests arriving on a loopback address
        remote_host = bottle.request.get_header("Host", "")
        try:
            host_name = remote_host.split(":")[0]
        except Exception:
            host_name = ""

        if host_name in _CSRF_LOCALHOST:
            return

        # Check Origin first, then Referer
        origin = bottle.request.get_header("Origin")
        referer = bottle.request.get_header("Referer")

        origin_host = _origin_host(origin) if origin else _origin_host(referer)

        if origin_host is None:
            raise bottle.HTTPError(403, "CSRF validation failed: missing Origin/Referer")

        if origin_host != host_name and origin_host not in _CSRF_LOCALHOST:
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
            self._hits[ip] = [t for t in timestamps if t > cutoff]
            if len(self._hits[ip]) >= self._max:
                return False
            self._hits[ip].append(now)
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


def install_rate_limiting(app: bottle.Bottle):
    """
    Per-IP sliding window rate limiter.  Returns 429 with Retry-After when
    the limit is exceeded.  The SSE stream endpoint is exempt.
    """
    limiter = _RateLimiter()

    @app.hook("before_request")
    def _rate_limit():
        if bottle.request.path == _SSE_STREAM_PATH:
            return

        # Respect X-Forwarded-For if present
        forwarded = bottle.request.get_header("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
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
        if provided != configured_key:
            raise bottle.HTTPError(401, "Invalid API key")


# ---------------------------------------------------------------------------
# Convenience installer
# ---------------------------------------------------------------------------

def install_security_middleware(app: bottle.Bottle, get_api_key=None):
    """Install all security middleware on the given Bottle app."""
    install_security_headers(app)
    install_csrf_protection(app)
    install_rate_limiting(app)
    if get_api_key is not None:
        install_api_key_auth(app, get_api_key)
