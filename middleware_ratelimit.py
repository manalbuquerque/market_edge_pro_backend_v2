import os
import re
import time
import asyncio
from typing import Dict, List, Pattern, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class TokenBucket:
    """
    Implementação simples de token bucket para rate limiting.
    """
    def __init__(self, rate: float, capacity: int) -> None:
        self.rate = rate  # tokens por segundo
        self.capacity = capacity
        self.tokens = capacity
        self.timestamp = time.monotonic()
        self._lock = asyncio.Lock()

    async def allow(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.timestamp
            # recarregar tokens
            self.tokens = min(
                self.capacity, self.tokens + elapsed * self.rate
            )
            self.timestamp = now
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, enabled: Optional[bool] = None) -> None:
        super().__init__(app)

        self.enabled = enabled if enabled is not None else os.getenv("RATE_LIMIT_ENABLED", "0") == "1"
        self.rps = float(os.getenv("RATE_LIMIT_RPS", "5"))  # requests por segundo
        self.burst = int(os.getenv("RATE_LIMIT_BURST", "10"))  # capacidade máxima

        # Por omissão aplica a todas as rotas (.*)
        raw_patterns = os.getenv("RATE_LIMIT_PATHS", ".*").strip()
        self._patterns: List[Pattern[str]] = []
        for p in [s for s in raw_patterns.split(",") if s.strip()]:
            try:
                self._patterns.append(re.compile(p.strip()))
            except re.error:
                pass

        # Dicionário chave → token bucket
        self.buckets: Dict[str, TokenBucket] = {}

        # Estratégia de chave
        self.by = os.getenv("RATE_LIMIT_BY", "apikey")

        print(
            {
                "evt": "ratelimit_init",
                "enabled": self.enabled,
                "rps": self.rps,
                "burst": self.burst,
                "patterns": [p.pattern for p in self._patterns],
                "by": self.by,
            }
        )

    def _apply_to_path(self, path: str) -> bool:
        for pat in self._patterns:
            if pat.search(path):
                return True
        return False

    def _key_for(self, scope) -> Optional[str]:
        headers = dict(scope.get("headers") or [])
        apikey = headers.get(b"x-api-key")
        if self.by == "apikey" and apikey:
            return apikey.decode()
        if self.by == "ip":
            client = scope.get("client")
            return client[0] if client else None
        if self.by == "path":
            return scope.get("path")
        return None

    async def dispatch(self, request, call_next):
        if not self.enabled:
            return await call_next(request)

        path = request.url.path
        if not self._apply_to_path(path):
            return await call_next(request)

        key = self._key_for(request.scope)
        if not key:
            # fallback para IP
            client = request.scope.get("client")
            key = client[0] if client else "unknown"

        bucket = self.buckets.get(key)
        if not bucket:
            bucket = TokenBucket(rate=self.rps, capacity=self.burst)
            self.buckets[key] = bucket

        allowed = await bucket.allow()
        if not allowed:
            retry_after = 1 / self.rps if self.rps > 0 else 1
            return JSONResponse(
                {"detail": "Too Many Requests"},
                status_code=429,
                headers={"Retry-After": str(int(retry_after))},
            )

        return await call_next(request)

