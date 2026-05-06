# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest

import bottle
from webtest import TestApp

from web.security import (
    _origin_tuple,
    _RateLimiter,
    install_api_key_auth,
    install_csrf_protection,
    install_rate_limiting,
    install_security_headers,
)


def _make_app_with_route():
    """Create a minimal Bottle app with a single POST/GET route for testing."""
    app = bottle.Bottle()

    @app.route("/test", method=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
    def test_route():
        return "ok"

    @app.route("/server/stream", method="GET")
    def stream_route():
        return "stream"

    @app.route("/server/config/get", method=["GET", "POST"])
    def config_get_route():
        return "config"

    @app.route("/server/protected", method=["GET", "POST"])
    def protected_route():
        return "protected"

    return app


# ---------------------------------------------------------------------------
# CSRF Protection Tests
# ---------------------------------------------------------------------------


class TestCsrfSafeMethodsExempt(unittest.TestCase):
    """Safe methods (GET, HEAD, OPTIONS) should pass without Origin check."""

    def setUp(self):
        self.app = _make_app_with_route()
        install_csrf_protection(self.app)
        self.test_app = TestApp(self.app)

    def test_get_without_origin_passes(self):
        resp = self.test_app.get("/test")
        self.assertEqual(resp.status_int, 200)

    def test_head_without_origin_passes(self):
        resp = self.test_app.head("/test")
        self.assertEqual(resp.status_int, 200)

    def test_options_without_origin_passes(self):
        resp = self.test_app.options("/test")
        self.assertEqual(resp.status_int, 200)


class TestCsrfLoopbackExemption(unittest.TestCase):
    """POST from loopback without proxy headers is exempt."""

    def setUp(self):
        self.app = _make_app_with_route()
        install_csrf_protection(self.app)
        self.test_app = TestApp(self.app)

    def test_post_from_localhost_without_proxy_headers_passes(self):
        """Loopback POST without X-Forwarded-For is exempt."""
        resp = self.test_app.post(
            "/test",
            extra_environ={"REMOTE_ADDR": "127.0.0.1"},
        )
        self.assertEqual(resp.status_int, 200)

    def test_post_from_ipv6_loopback_without_proxy_headers_passes(self):
        """IPv6 loopback POST is also exempt."""
        resp = self.test_app.post(
            "/test",
            extra_environ={"REMOTE_ADDR": "::1"},
        )
        self.assertEqual(resp.status_int, 200)

    def test_post_from_localhost_string_without_proxy_headers_passes(self):
        """'localhost' string also counts as loopback."""
        resp = self.test_app.post(
            "/test",
            extra_environ={"REMOTE_ADDR": "localhost"},
        )
        self.assertEqual(resp.status_int, 200)

    def test_post_from_loopback_with_x_forwarded_for_is_checked(self):
        """Proxied traffic through loopback IS checked for CSRF."""
        resp = self.test_app.post(
            "/test",
            headers={"X-Forwarded-For": "10.0.0.1"},
            extra_environ={"REMOTE_ADDR": "127.0.0.1"},
            expect_errors=True,
        )
        self.assertEqual(resp.status_int, 403)

    def test_post_from_loopback_with_forwarded_header_is_checked(self):
        """Forwarded header also triggers CSRF check on loopback."""
        resp = self.test_app.post(
            "/test",
            headers={"Forwarded": "for=10.0.0.1"},
            extra_environ={"REMOTE_ADDR": "127.0.0.1"},
            expect_errors=True,
        )
        self.assertEqual(resp.status_int, 403)


class TestCsrfOriginMatching(unittest.TestCase):
    """POST with matching/mismatched Origin."""

    def setUp(self):
        self.app = _make_app_with_route()
        install_csrf_protection(self.app)
        self.test_app = TestApp(self.app)

    def test_matching_origin_passes(self):
        resp = self.test_app.post(
            "/test",
            headers={
                "Origin": "http://example.com",
                "Host": "example.com",
            },
            extra_environ={"REMOTE_ADDR": "10.0.0.1"},
        )
        self.assertEqual(resp.status_int, 200)

    def test_mismatched_origin_returns_403(self):
        resp = self.test_app.post(
            "/test",
            headers={
                "Origin": "http://evil.com",
                "Host": "example.com",
            },
            extra_environ={"REMOTE_ADDR": "10.0.0.1"},
            expect_errors=True,
        )
        self.assertEqual(resp.status_int, 403)

    def test_referer_fallback_when_origin_absent(self):
        """When Origin is missing, Referer is used for CSRF check."""
        resp = self.test_app.post(
            "/test",
            headers={
                "Referer": "http://example.com/page",
                "Host": "example.com",
            },
            extra_environ={"REMOTE_ADDR": "10.0.0.1"},
        )
        self.assertEqual(resp.status_int, 200)

    def test_mismatched_referer_returns_403(self):
        resp = self.test_app.post(
            "/test",
            headers={
                "Referer": "http://evil.com/page",
                "Host": "example.com",
            },
            extra_environ={"REMOTE_ADDR": "10.0.0.1"},
            expect_errors=True,
        )
        self.assertEqual(resp.status_int, 403)

    def test_neither_origin_nor_referer_returns_403(self):
        resp = self.test_app.post(
            "/test",
            headers={"Host": "example.com"},
            extra_environ={"REMOTE_ADDR": "10.0.0.1"},
            expect_errors=True,
        )
        self.assertEqual(resp.status_int, 403)
        self.assertIn("missing Origin/Referer", resp.text)


class TestCsrfPortNormalization(unittest.TestCase):
    """Port normalization: default ports (80/443) are treated as equivalent."""

    def setUp(self):
        self.app = _make_app_with_route()
        install_csrf_protection(self.app)
        self.test_app = TestApp(self.app)

    def test_explicit_port_80_matches_implicit(self):
        """http://example.com:80 should match http://example.com."""
        resp = self.test_app.post(
            "/test",
            headers={
                "Origin": "http://example.com:80",
                "Host": "example.com",
            },
            extra_environ={"REMOTE_ADDR": "10.0.0.1"},
        )
        self.assertEqual(resp.status_int, 200)

    def test_explicit_port_443_matches_implicit_https(self):
        """https://example.com:443 should match https://example.com."""
        resp = self.test_app.post(
            "/test",
            headers={
                "Origin": "https://example.com:443",
                "Host": "example.com",
            },
            extra_environ={"REMOTE_ADDR": "10.0.0.1"},
        )
        self.assertEqual(resp.status_int, 200)


class TestOriginTupleHelper(unittest.TestCase):
    """Tests for the _origin_tuple parsing helper."""

    def test_normal_url(self):
        result = _origin_tuple("http://example.com")
        self.assertEqual(result, ("http", "example.com", 80))

    def test_url_with_port(self):
        result = _origin_tuple("http://example.com:8080")
        self.assertEqual(result, ("http", "example.com", 8080))

    def test_https_default_port(self):
        result = _origin_tuple("https://secure.example.com")
        self.assertEqual(result, ("https", "secure.example.com", 443))

    def test_none_input(self):
        result = _origin_tuple(None)
        self.assertIsNone(result)

    def test_empty_string(self):
        result = _origin_tuple("")
        self.assertIsNone(result)

    def test_malformed_url_returns_none(self):
        result = _origin_tuple("not-a-url")
        self.assertIsNone(result)

    def test_scheme_only_returns_none(self):
        result = _origin_tuple("http://")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Rate Limiting Tests
# ---------------------------------------------------------------------------


class TestRateLimiterUnit(unittest.TestCase):
    """Direct tests on the _RateLimiter class."""

    def test_below_limit_requests_allowed(self):
        limiter = _RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            self.assertTrue(limiter.is_allowed("10.0.0.1"))

    def test_exceeding_limit_rejected(self):
        limiter = _RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            self.assertTrue(limiter.is_allowed("10.0.0.1"))
        self.assertFalse(limiter.is_allowed("10.0.0.1"))

    def test_per_ip_independence(self):
        limiter = _RateLimiter(max_requests=2, window_seconds=60)
        self.assertTrue(limiter.is_allowed("10.0.0.1"))
        self.assertTrue(limiter.is_allowed("10.0.0.1"))
        self.assertFalse(limiter.is_allowed("10.0.0.1"))
        # Different IP should still be allowed
        self.assertTrue(limiter.is_allowed("10.0.0.2"))
        self.assertTrue(limiter.is_allowed("10.0.0.2"))

    def test_retry_after_returns_positive_value(self):
        limiter = _RateLimiter(max_requests=1, window_seconds=60)
        limiter.is_allowed("10.0.0.1")
        limiter.is_allowed("10.0.0.1")  # rejected
        retry = limiter.retry_after("10.0.0.1")
        self.assertGreater(retry, 0)

    def test_retry_after_returns_zero_for_unknown_ip(self):
        limiter = _RateLimiter(max_requests=5, window_seconds=60)
        # No requests yet for this IP
        retry = limiter.retry_after("10.0.0.99")
        self.assertEqual(retry, 0)

    def test_stale_entry_sweep(self):
        """Stale entries should be swept after sweep_interval."""
        limiter = _RateLimiter(max_requests=2, window_seconds=1, sweep_interval=0)
        limiter.is_allowed("10.0.0.1")
        limiter.is_allowed("10.0.0.1")
        # Manually expire all timestamps
        with limiter._lock:
            limiter._hits["10.0.0.1"] = [0.0]  # ancient timestamp
            limiter._last_sweep = 0.0  # force sweep on next call
        # Next call triggers sweep and allows the request
        self.assertTrue(limiter.is_allowed("10.0.0.1"))


class TestRateLimitingMiddleware(unittest.TestCase):
    """Tests for the rate limiting Bottle middleware."""

    def test_sse_stream_endpoint_exempt(self):
        app = _make_app_with_route()
        install_rate_limiting(app)
        test_app = TestApp(app)
        # SSE stream should never be rate limited
        for _ in range(200):
            resp = test_app.get("/server/stream")
            self.assertEqual(resp.status_int, 200)

    def test_disable_flag_skips_limiting(self):
        app = _make_app_with_route()
        install_rate_limiting(app, disable=True)
        test_app = TestApp(app)
        # With disable=True, no rate limiting should apply at all
        for _ in range(200):
            resp = test_app.get("/test")
            self.assertEqual(resp.status_int, 200)

    def test_rate_limit_returns_429_with_retry_after(self):
        app = _make_app_with_route()
        limiter = _RateLimiter(max_requests=2, window_seconds=60)

        @app.hook("before_request")
        def _rate_limit():
            ip = bottle.request.environ.get("REMOTE_ADDR", "127.0.0.1")
            if not limiter.is_allowed(ip):
                retry = limiter.retry_after(ip)
                resp = bottle.HTTPError(429, "Rate limit exceeded")
                resp.headers["Retry-After"] = str(retry)
                raise resp

        test_app = TestApp(app)
        test_app.get("/test", extra_environ={"REMOTE_ADDR": "10.0.0.1"})
        test_app.get("/test", extra_environ={"REMOTE_ADDR": "10.0.0.1"})
        resp = test_app.get(
            "/test",
            extra_environ={"REMOTE_ADDR": "10.0.0.1"},
            expect_errors=True,
        )
        self.assertEqual(resp.status_int, 429)
        self.assertIn("Retry-After", resp.headers)

    def test_x_forwarded_for_used_when_trusted(self):
        app = _make_app_with_route()
        limiter = _RateLimiter(max_requests=2, window_seconds=60)

        @app.hook("before_request")
        def _rate_limit():
            ip = None
            forwarded = bottle.request.get_header("X-Forwarded-For")
            if forwarded:
                ip = forwarded.split(",")[0].strip()
            if not ip:
                ip = bottle.request.environ.get("REMOTE_ADDR", "127.0.0.1")
            if not limiter.is_allowed(ip):
                raise bottle.HTTPError(429, "Rate limit exceeded")

        test_app = TestApp(app)

        # Requests with X-Forwarded-For should use the forwarded IP
        test_app.get(
            "/test",
            headers={"X-Forwarded-For": "192.168.1.100"},
            extra_environ={"REMOTE_ADDR": "127.0.0.1"},
        )
        test_app.get(
            "/test",
            headers={"X-Forwarded-For": "192.168.1.100"},
            extra_environ={"REMOTE_ADDR": "127.0.0.1"},
        )
        # Third request from same forwarded IP should be rejected
        resp = test_app.get(
            "/test",
            headers={"X-Forwarded-For": "192.168.1.100"},
            extra_environ={"REMOTE_ADDR": "127.0.0.1"},
            expect_errors=True,
        )
        self.assertEqual(resp.status_int, 429)

        # But a different forwarded IP should still be allowed
        resp = test_app.get(
            "/test",
            headers={"X-Forwarded-For": "192.168.1.200"},
            extra_environ={"REMOTE_ADDR": "127.0.0.1"},
        )
        self.assertEqual(resp.status_int, 200)


# ---------------------------------------------------------------------------
# Security Headers Tests
# ---------------------------------------------------------------------------


class TestSecurityHeaders(unittest.TestCase):
    """Every response should include security headers."""

    def setUp(self):
        self.app = _make_app_with_route()
        install_security_headers(self.app)
        self.test_app = TestApp(self.app)

    def test_nosniff_header_present(self):
        resp = self.test_app.get("/test")
        self.assertEqual(resp.headers["X-Content-Type-Options"], "nosniff")

    def test_x_frame_options_header_present(self):
        resp = self.test_app.get("/test")
        self.assertEqual(resp.headers["X-Frame-Options"], "DENY")

    def test_csp_header_present(self):
        resp = self.test_app.get("/test")
        csp = resp.headers["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src 'self'", csp)

    def test_referrer_policy_header_present(self):
        resp = self.test_app.get("/test")
        self.assertEqual(
            resp.headers["Referrer-Policy"],
            "strict-origin-when-cross-origin",
        )

    def test_headers_on_post_response(self):
        """Security headers should be added to POST responses too."""
        # Need CSRF to pass — use loopback
        install_csrf_protection(self.app)
        test_app = TestApp(self.app)
        resp = test_app.post(
            "/test",
            extra_environ={"REMOTE_ADDR": "127.0.0.1"},
        )
        self.assertEqual(resp.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(resp.headers["X-Frame-Options"], "DENY")


# ---------------------------------------------------------------------------
# API Key Authentication Tests
# ---------------------------------------------------------------------------


class TestApiKeyAuthDisabled(unittest.TestCase):
    """When API key is empty, auth is disabled."""

    def setUp(self):
        self.app = _make_app_with_route()
        install_api_key_auth(self.app, get_api_key=lambda: "")
        self.test_app = TestApp(self.app)

    def test_empty_key_disables_auth(self):
        resp = self.test_app.get("/server/protected")
        self.assertEqual(resp.status_int, 200)

    def test_empty_key_allows_any_server_route(self):
        resp = self.test_app.get("/server/stream")
        self.assertEqual(resp.status_int, 200)


class TestApiKeyAuthEnabled(unittest.TestCase):
    """When API key is set, protected routes require it."""

    def setUp(self):
        self.api_key = "test-secret-key-12345"
        self.app = _make_app_with_route()
        install_api_key_auth(self.app, get_api_key=lambda: self.api_key)
        self.test_app = TestApp(self.app)

    def test_valid_key_passes(self):
        resp = self.test_app.get(
            "/server/protected",
            headers={"X-Api-Key": self.api_key},
        )
        self.assertEqual(resp.status_int, 200)

    def test_invalid_key_returns_401(self):
        resp = self.test_app.get(
            "/server/protected",
            headers={"X-Api-Key": "wrong-key"},
            expect_errors=True,
        )
        self.assertEqual(resp.status_int, 401)
        self.assertIn("Invalid API key", resp.text)

    def test_missing_key_returns_401(self):
        resp = self.test_app.get(
            "/server/protected",
            expect_errors=True,
        )
        self.assertEqual(resp.status_int, 401)
        self.assertIn("API key required", resp.text)

    def test_non_server_paths_unprotected(self):
        """Paths not starting with /server/ don't require API key."""
        resp = self.test_app.get("/test")
        self.assertEqual(resp.status_int, 200)

    def test_config_get_exempt(self):
        """/server/config/get is exempt for frontend bootstrapping."""
        resp = self.test_app.get("/server/config/get")
        self.assertEqual(resp.status_int, 200)

    def test_sse_accepts_query_param(self):
        """SSE stream endpoint accepts api_key as query parameter."""
        resp = self.test_app.get(f"/server/stream?api_key={self.api_key}")
        self.assertEqual(resp.status_int, 200)

    def test_sse_rejects_invalid_query_param(self):
        resp = self.test_app.get(
            "/server/stream?api_key=wrong",
            expect_errors=True,
        )
        self.assertEqual(resp.status_int, 401)

    def test_sse_header_also_works(self):
        """SSE stream also accepts the key via X-Api-Key header."""
        resp = self.test_app.get(
            "/server/stream",
            headers={"X-Api-Key": self.api_key},
        )
        self.assertEqual(resp.status_int, 200)
