from __future__ import annotations
import os, time
from typing import Iterable, Set
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from sqlalchemy import text
from db_mep_v2 import engine  # existing engine

PUBLIC_DEFAULT: Set[str] = {"/health", "/healthz", "/ready", "/readyz", "/metrics", "/docs", "/openapi.json"}

def _load_env_keys() -> Set[str]:
    raw = os.getenv("API_KEYS", "")
    return {k.strip() for k in raw.replace(";", ",").split(",") if k.strip()}

class ApiKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, public_paths: Iterable[str] | None = None):
        super().__init__(app)
        self.enabled = os.getenv("APIKEY_ENABLED", "1") not in ("0", "false", "False")
        self.public = set(public_paths or []) | PUBLIC_DEFAULT
        self.env_keys = _load_env_keys()

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        path = (request.url.path or "/").rstrip("/")
        if path in self.public or any(path.startswith(p) for p in ("/docs", "/openapi")):
            return await call_next(request)

        key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if not key:
            return JSONResponse({"detail": "invalid or missing API key"}, status_code=401)

        # 1) Fast path: env keys
        if key in self.env_keys:
            return await call_next(request)

        # 2) DB path: active + not expired
        try:
            with engine.begin() as con:
                row = con.execute(
                    text("""
                        SELECT key FROM api_keys
                        WHERE key = :k
                          AND status = 'active'
                          AND (expires_at IS NULL OR expires_at > NOW())
                        LIMIT 1
                    """),
                    {"k": key},
                ).first()
                if row:
                    con.execute(text("UPDATE api_keys SET last_used_at=NOW(), updated_at=NOW() WHERE key=:k"), {"k": key})
                    return await call_next(request)
        except Exception:
            # If DB is down, keep behavior consistent with security: deny (but do not 500)
            pass

        return JSONResponse({"detail": "invalid or missing API key"}, status_code=401)
