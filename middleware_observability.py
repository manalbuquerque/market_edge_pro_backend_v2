# middleware_observability.py
from __future__ import annotations
import time, uuid, json, os
from typing import Callable
from starlette.types import ASGIApp, Receive, Scope, Send

class ObservabilityMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app
        self.enabled = os.getenv("OBS_ENABLED", "1") not in ("0", "false", "False")

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if not self.enabled or scope["type"] != "http":
            return await self.app(scope, receive, send)

        start = time.perf_counter()
        req_id = str(uuid.uuid4())
        method = scope.get("method")
        path = scope.get("path")
        client = (scope.get("client") or ("", ""))[0]

        status_code_holder = {"code": 0}
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code_holder["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            dur_ms = round((time.perf_counter() - start) * 1000.0, 2)
            log = {
                "evt": "http_access",
                "req_id": req_id,
                "method": method,
                "path": path,
                "status": status_code_holder["code"],
                "dur_ms": dur_ms,
                "client": client,
            }
            print(json.dumps(log, ensure_ascii=False))
