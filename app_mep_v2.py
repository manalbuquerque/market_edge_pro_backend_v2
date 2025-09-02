# app_mep_v2.py
# Market Edge Pro v2 — FastAPI entrypoint
# Mounts data, backtests, screener, metrics, and signals routers.
# Avoids route collisions by mounting the legacy data router at /v2/legacy.

from __future__ import annotations

import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# -----------------------------
# Logging
# -----------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("mep.app")

# -----------------------------
# Routers (import defensively so the app still boots if one fails)
# -----------------------------
try:
    # Official market/data endpoints
    from services_market_mep_v2 import router as data_router_v2
    logger.info("Loaded services_market_mep_v2 router.")
except Exception as e:
    data_router_v2 = None  # type: ignore
    logger.exception("Failed to load services_market_mep_v2 router: %s", e)

try:
    # Legacy data endpoints
    from routers_data_mep_v2 import router as data_router_legacy
    logger.info("Loaded routers_data_mep_v2 (legacy) router.")
except Exception as e:
    data_router_legacy = None  # type: ignore
    logger.warning("No legacy data router: %s", e)

try:
    from routers_backtests_mep_v2 import router as bt_router_v2
    logger.info("Loaded routers_backtests_mep_v2.")
except Exception as e:
    bt_router_v2 = None  # type: ignore
    logger.warning("No backtests router: %s", e)

try:
    from routers_screener_mep_v2 import router as screener_router_v2
    logger.info("Loaded routers_screener_mep_v2.")
except Exception as e:
    screener_router_v2 = None  # type: ignore
    logger.warning("No screener router: %s", e)

try:
    from routers_metrics_mep_v2 import router as metrics_router_v2
    logger.info("Loaded routers_metrics_mep_v2.")
except Exception as e:
    metrics_router_v2 = None  # type: ignore
    logger.warning("No metrics router: %s", e)

try:
    from routers_signals_mep_v2 import router as signals_router_v2
    logger.info("Loaded routers_signals_mep_v2.")
except Exception as e:
    signals_router_v2 = None  # type: ignore
    logger.warning("No signals router: %s", e)

# -----------------------------
# App factory
# -----------------------------
def create_app() -> FastAPI:
    app = FastAPI(
        title="Market Edge Pro v2",
        version=os.getenv("APP_VERSION", "2.0.0"),
        debug=os.getenv("APP_DEBUG", "true").lower() == "true",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS
    allowed_origins = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in allowed_origins if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers (mount all under /v2 except legacy at /v2/legacy)
    if data_router_v2:
        app.include_router(data_router_v2, prefix="/v2")
        logger.info("Mounted data_router_v2 at /v2.")
    if data_router_legacy:
        app.include_router(data_router_legacy, prefix="/v2/legacy")
        logger.info("Mounted data_router_legacy at /v2/legacy.")
    if bt_router_v2:
        app.include_router(bt_router_v2, prefix="/v2")
        logger.info("Mounted bt_router_v2 at /v2.")
    if screener_router_v2:
        app.include_router(screener_router_v2, prefix="/v2")
        logger.info("Mounted screener_router_v2 at /v2.")
    if metrics_router_v2:
        app.include_router(metrics_router_v2, prefix="/v2")
        logger.info("Mounted metrics_router_v2 at /v2.")
    if signals_router_v2:
        app.include_router(signals_router_v2, prefix="/v2")
        logger.info("Mounted signals_router_v2 at /v2.")

    # Health/meta
    @app.get("/", tags=["meta"])
    def root() -> dict:
        return {"name": "Market Edge Pro v2", "ok": True}

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict:
        return {"ok": True}

    @app.get("/version", tags=["meta"])
    def version() -> dict:
        return {"version": app.version}

    return app

# -----------------------------
# ASGI app
# -----------------------------
app = create_app()

# Run locally:
# uvicorn app_mep_v2:app --reload --port 8080
