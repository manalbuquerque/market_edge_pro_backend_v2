# middleware_apikey.py
from __future__ import annotations

import os
import json
import logging
import traceback
import hmac
from typing import Iterable, Set, List, Tuple
from starlette.types import ASGIApp, Receive, Scope, Send

_log = logging.getLogger("apikey")
if not _log.handlers:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

class ApiKeyMiddleware:
    """
    Require header X-API-Key to be in the allowed set.
    Configure via env (APIKEY_ENABLED, APIKEYS) or override with kwargs.

    Additions (kept and extended):
    - PUBLIC_PATHS allowlist (bypass auth) -> env: APIKEY_PUBLIC_PATHS
    - PUBLIC_PREFIXES allowlist (/docs, /openapi...) -> env: APIKEY_PUBLIC_PREFIXES
    - Accept alternative envs for keys: APIKEYS, API_KEYS, API_KEY
    - Timing-safe key comparison
    - Path normalization (strip trailing '/')
    - Bypass for CORS preflight (OPTIONS)
    - Optional Authorization header support: "Authorization: ApiKey <token>"
    - Do NOT mask downstream exceptions (only auth errors handled here)
    """

    def __init__(self, app: ASGIApp, *, enabled: bool | None = None, keys: Iterable[str] | None = None):
        self.app = app

        # Enabled flag (truthy values)
        env_enabled_raw = os.getenv("APIKEY_ENABLED", "0")
        self.enabled = (
            bool(enabled) if enabled is not None else env_enabled_raw.lower() in {"1", "true", "t", "yes", "on"}
        )

        # Collect keys from multiple env vars
        def _split(env_name: str) -> Set[str]:
            return {k.strip() for k in os.getenv(env_name, "").split(",") if k.strip()}

        env_keys = _split("APIKEYS") | _split("API_KEYS") | _split("API_KEY")
        provided_keys = set(keys) if keys is not None else env_keys
        self.allowed: Set[str] = provided_keys if self.enabled else set()

        # Public paths (exact matches)
        default_public: List[str] = [
            "/health", "/healthz", "/ready", "/readyz", "/metrics", "/docs", "/openapi.json"
        ]
        extra_public: List[str] = [p.strip() for p in os.getenv("APIKEY_PUBLIC_PATHS", "").split(",") if p.strip()]
        self.public_paths: Set[str] = set(default_public + extra_public)

        # Public prefixes
        default_prefixes: List[str] = ["/docs", "/openapi"]
        extra_prefixes: List[str] = [
            p.strip() for p in os.getenv("APIKEY_PUBLIC_PREFIXES", "").split(",") if p.strip()
        ]
        self.public_prefixes: List[str] = list(dict.fromkeys(default_prefixes + extra_prefixes))  # dedup keep order

        _log.info(
            "apikey_init enabled=%s keys=%d public=%s prefixes=%s",
            self.enabled, len(self.allowed), sorted(self.public_paths), self.public_prefixes
        )

    @staticmethod
    def _norm_path(path: str) -> str:
        if not path:
            return "/"
        p = path.rstrip("/")
        return p or "/"

    @staticmethod
    def _extract_key_from_headers(raw_headers: List[Tuple[bytes, bytes]]) -> str:
        key = ""
        auth = ""
        for name, value in raw_headers or []:
            if not name:
                continue
            lower = name.lower()
            if lower == b"x-api-key":
                try:
                    key = value.decode("utf-8", "ignore")
                except Exception:
                    key = ""
            elif lower == b"authorization":
                try:
                    auth = value.decode("utf-8", "ignore")
                except Exception:
                    auth = ""
        # Prefer X-API-Key; fallback Authorization: ApiKey <token>
        if key:
            return key
        if auth:
            # Formats aceites: "ApiKey token", "apikey token"
            parts = auth.strip().split()
            if len(parts) == 2 and parts[0].lower() == "apikey":
                return parts[1]
        return ""

    def _is_public(self, path: str) -> bool:
        norm = self._norm_path(path)
        if norm in self.public_paths:
            return True
        for pref in self.public_prefixes:
            if norm.startswith(pref):
                return True
        return False

    def _is_valid(self, key: str) -> bool:
        # Timing-safe comparison against any allowed key
        if not key or not self.allowed:
            return False
        for allowed in self.allowed:
            if hmac.compare_digest(key, allowed):
                return True
        return False

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        # Only HTTP
        if scope.get("type") != "http" or not self.enabled:
            return await self.app(scope, receive, send)

        try:
            # Bypass CORS preflight early
            if (scope.get("method") or "").upper() == "OPTIONS":
                return await self.app(scope, receive, send)

            path = scope.get("path") or "/"
            if self._is_public(path):
                # Bypass for health/ready/metrics/docs/openapi
                return await self.app(scope, receive, send)

            # Extract API key
            key = self._extract_key_from_headers(scope.get("headers") or [])
            if self._is_valid(key):
                return await self.app(scope, receive, send)

            # 401 JSON
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"cache-control", b"no-store"),
                    (b"www-authenticate", b'ApiKey realm="market-edge-pro"'),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": json.dumps({"detail": "invalid or missing API key"}).encode(),
            })
        except Exception:
            # Only catch middleware errors; never mask downstream application exceptions
            tb = traceback.format_exc(limit=3)
            _log.error("apikey_error %s", tb)
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({
                "type": "http.response.body",
                "body": json.dumps({"detail": "internal auth error"}).encode(),
            })