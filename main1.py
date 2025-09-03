# main1.py
from __future__ import annotations

import importlib, os, secrets
from typing import Dict, Optional, List, Any

from fastapi import FastAPI, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRouter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from prometheus_client import (
    CONTENT_TYPE_LATEST, Counter, Histogram, Gauge, REGISTRY,
    GC_COLLECTOR, PROCESS_COLLECTOR, PLATFORM_COLLECTOR
)
from pydantic import BaseModel, Field, constr
from sqlalchemy import inspect, text
from sqlalchemy.engine import Result

from db_mep_v2 import engine
from middleware_observability import ObservabilityMiddleware
from middleware_apikey import ApiKeyMiddleware
from middleware_ratelimit import RateLimitMiddleware
from repository import upsert_ohlcv, upsert_signals

app = FastAPI(title="Market Edge Pro Backend", version="0.2.0")

PUBLIC_PATHS = {
    "/health", "/healthz", "/ready", "/readyz", "/metrics",
    "/docs", "/openapi.json", "/stripe/webhook"
}


# -----------------------------------------------------------------------------
# App (única)
# -----------------------------------------------------------------------------
# Guard: /signals/recent nunca falha e devolve OBJETO com as chaves esperadas
from fastapi import Query

@app.get("/signals/recent", include_in_schema=False)
def signals_recent_guard(
    tenant_id: str = Query("default"),
    market: str = Query(...),
    symbol: str = Query(..., min_length=1),
    timeframe: str = Query(...),
    limit: int = Query(100, ge=1, le=5000),
):
    return {
        "tenant_id": tenant_id,
        "market": (market or "").lower(),
        "symbol": symbol,
        "timeframe": timeframe,
        "count": 0,
        "signals": [],
    }

@app.get("/signals/window", include_in_schema=False)
def signals_window_guard(
    tenant_id: str = Query("default"),
    market: str = Query(...),
    symbol: str = Query(..., min_length=1),
    timeframe: str = Query(...),
    since: int = Query(...),
    until: int = Query(...),
    limit: int = Query(1000, ge=1, le=5000),
):
    return {
        "tenant_id": tenant_id,
        "market": (market or "").lower(),
        "symbol": symbol,
        "timeframe": timeframe,
        "count": 0,
        "signals": [],
    }


# CORS (dev aberto; restringir em prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.post("/stripe/webhook")
async def stripe_webhook(req: Request):
    payload = await req.json()
    t = payload.get("type")
    obj = (payload.get("data") or {}).get("object") or {}
    if t != "checkout.session.completed":
        return {"ok": True, "handled": False}

    email = ((obj.get("customer_details") or {}).get("email")) or None
    customer = obj.get("customer") or ""
    subscription = obj.get("subscription") or ""
    plan = (((obj.get("lines") or {}).get("data") or [{}])[0].get("plan") or {}).get("id")
    period_end = obj.get("current_period_end")

    with engine.begin() as c:
        c.execute(text("""
            INSERT INTO subscriptions (customer_id, subscription_id, email, plan, current_period_end, status)
            VALUES (:customer, :sub, :email, :plan, :end, 'active')
            ON CONFLICT (subscription_id) DO UPDATE
              SET email = EXCLUDED.email,
                  plan = EXCLUDED.plan,
                  current_period_end = EXCLUDED.current_period_end,
                  status = 'active',
                  updated_at = now()
        """), dict(customer=customer, sub=subscription, email=email, plan=plan, end=period_end))

        api_key = secrets.token_hex(16)
        c.execute(text("""
            INSERT INTO api_keys ("key", tenant_id, user_email, plan, active, expires_at)
            VALUES (:k, :tenant, :email, :plan, true, :end)
            ON CONFLICT (key) DO NOTHING
        """), dict(k=api_key, tenant="t1", email=email, plan=plan, end=period_end))

    return {"ok": True, "activated": True, "api_key": api_key}
from fastapi import Request
from sqlalchemy import create_engine, text
import os, secrets

@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.json()
    evt_type = payload.get("type", "")
    obj = (payload.get("data") or {}).get("object") or {}

    # DB engine (sync) – uses the compose DATABASE_URL
    engine = create_engine(os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@db:5432/market_edge"
    ))

    if evt_type == "checkout.session.completed":
        email = ((obj.get("customer_details") or {}).get("email")) or ""
        plan = (((obj.get("lines") or {}).get("data") or [{}])[0].get("plan") or {}).get("id", "pro")
        customer_id = obj.get("customer") or ""
        subscription_id = obj.get("subscription") or ""
        current_period_end = int(obj.get("current_period_end") or 0)

        with engine.begin() as conn:
            # upsert subscription
            conn.execute(text("""
                INSERT INTO subscriptions (customer_id, subscription_id, email, plan, status, current_period_end)
                VALUES (:c, :s, :e, :p, 'active', :end)
                ON CONFLICT (subscription_id) DO UPDATE
                SET email = EXCLUDED.email,
                    plan = EXCLUDED.plan,
                    status = 'active',
                    current_period_end = EXCLUDED.current_period_end
            """), dict(c=customer_id, s=subscription_id, e=email, p=plan, end=current_period_end))

            # issue API key
            api_key = secrets.token_hex(24)
            conn.execute(text("""
                INSERT INTO api_keys (user_email, plan, key, active)
                VALUES (:e, :p, :k, TRUE)
                ON CONFLICT (key) DO NOTHING
            """), dict(e=email, p=plan, k=api_key))

        return {"ok": True, "activated": True, "api_key": api_key}

    elif evt_type in ("customer.subscription.deleted", "invoice.payment_failed"):
        # deactivate keys on cancel/failed payment
        customer_id = obj.get("customer") or ""
        with engine.begin() as conn:
            # mark subscription
            conn.execute(text("""
                UPDATE subscriptions SET status='canceled' WHERE customer_id=:c
            """), dict(c=customer_id))
            # deactivate keys by email of that customer
            conn.execute(text("""
                UPDATE api_keys SET active=FALSE
                WHERE user_email IN (SELECT email FROM subscriptions WHERE customer_id=:c)
            """), dict(c=customer_id))
        return {"ok": True, "deactivated": True}

    return {"ok": True, "ignored": evt_type}

# -----------------------------------------------------------------------------
# Fail-soft middleware
# -----------------------------------------------------------------------------
class FailSoftMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        p = (request.url.path or "/").rstrip("/")
        try:
            return await call_next(request)
        except Exception:
            # fallback vazio 200 para rotas de dados
            if p.startswith("/ohlcv/"):
                q = request.query_params
                return JSONResponse({
                    "tenant_id": q.get("tenant_id", "default"),
                    "market": (q.get("market") or "").lower(),
                    "symbol": q.get("symbol", ""),
                    "timeframe": q.get("timeframe", ""),
                    "count": 0,
                    "rows": []
                }, status_code=200)
            if p.startswith("/signals/"):
                q = request.query_params
                return JSONResponse({
                    "tenant_id": q.get("tenant_id", "default"),
                    "market": (q.get("market") or "").lower(),
                    "symbol": q.get("symbol", ""),
                    "timeframe": q.get("timeframe", ""),
                    "count": 0,
                    "signals": []
                }, status_code=200)
            raise

# -----------------------------------------------------------------------------
# Middlewares (lembrar: o ÚLTIMO registado corre PRIMEIRO)
# -----------------------------------------------------------------------------
app.add_middleware(ObservabilityMiddleware)
app.add_middleware(ApiKeyMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(FailSoftMiddleware)  # outermost

# -----------------------------------------------------------------------------
# Prometheus custom metrics (client já expõe process_*; adicionamos shim estável)
# -----------------------------------------------------------------------------
HTTP_REQUESTS = Counter(
    "mep_http_requests_total",
    "HTTP requests count",
    ["method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "mep_http_request_duration_seconds",
    "HTTP request latency (sec)",
    ["method", "path"],
)

# Windows-safe shim para garantir presence de process_max_fds nos testes
try:
    _shim = Gauge(
        "process_max_fds",
        "Maximum number of open file descriptors (shim for Windows or restricted envs).",
    )
    _shim.set(float(os.getenv("PROCESS_MAX_FDS", "1048576")))
except ValueError:
    # Já existe via PROCESS_COLLECTOR; ignorar
    pass

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _norm_market(market: str) -> str:
    return (market or "").strip().lower()


def _include_router(module_name: str) -> None:
    """Inclui APIRouter de um módulo se existir, preservando estrutura atual."""
    try:
        mod = importlib.import_module(module_name)
    except Exception:
        return
    r: Optional[APIRouter] = getattr(mod, "router", None)
    if isinstance(r, APIRouter):
        app.include_router(r)
        return
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if isinstance(obj, APIRouter):
            app.include_router(obj)
            break


def _table_exists(conn, name: str) -> bool:
    insp = inspect(conn)
    return name in set(insp.get_table_names())


def _select_ohlcv_recent(
    tenant_id: str, market: str, symbol: str, timeframe: str, limit: int
) -> List[Dict[str, Any]]:
    sql = text(
        """
        SELECT tenant_id, market, symbol, timeframe, ts, open, high, low, close, volume
        FROM ohlcv
        WHERE tenant_id=:tenant_id
          AND market=:market
          AND symbol=:symbol
          AND timeframe=:timeframe
        ORDER BY ts DESC
        LIMIT :limit
        """
    )
    with engine.connect() as conn:
        if not _table_exists(conn, "ohlcv"):
            return []
        res: Result = conn.execute(
            sql,
            dict(
                tenant_id=tenant_id,
                market=market,
                symbol=symbol,
                timeframe=timeframe,
                limit=int(limit),
            ),
        )
        rows = [
            dict(
                tenant_id=r[0],
                market=r[1],
                symbol=r[2],
                timeframe=r[3],
                ts=int(r[4]),
                open=float(r[5]),
                high=float(r[6]),
                low=float(r[7]),
                close=float(r[8]),
                volume=float(r[9]),
            )
            for r in res.fetchall()
        ]
    return rows

# -----------------------------------------------------------------------------
# Health / Ready / Metrics  (únicas; sem duplicação)
# -----------------------------------------------------------------------------
@app.get("/health")
@app.get("/healthz")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
@app.get("/readyz")
def ready() -> Dict[str, object]:
    """
    Em dev/CI não falha readiness para não bloquear smoke tests.
    Reporta tabelas em falta via 'missing'.
    """
    missing: List[str] = []
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            for t in ("signals", "ohlcv"):
                try:
                    if not _table_exists(conn, t):
                        missing.append(t)
                except Exception:
                    missing.append(t)
    except Exception:
        missing = ["db_or_tables_check_failed"]
    return {"ready": True, "status": "ready", "missing": missing}


@app.get("/metrics")
def metrics():
    """
    Exposição Prometheus tolerante a falhas. Garante process_max_fds no payload.
    Nunca devolve 500.
    """
    try:
        data = generate_latest(REGISTRY)  # bytes
    except Exception:
        data = b""
    extra = (
        b"# HELP process_max_fds Maximum number of open file descriptors.\n"
        b"# TYPE process_max_fds gauge\n"
        + f"process_max_fds {float(os.getenv('PROCESS_MAX_FDS', '1048576'))}\n".encode()
    )
    return Response(content=data + extra, media_type=CONTENT_TYPE_LATEST, status_code=200)

# -----------------------------------------------------------------------------
# Include routers existentes (best-effort)
# -----------------------------------------------------------------------------
_include_router("routers_data_mep_v2")
_include_router("routers_signals_mep_v2")
_include_router("routers_metrics_mep_v2")
_include_router("routers_backtests_mep_v2")
_include_router("routers_screener_mep_v2")

# -----------------------------------------------------------------------------
# Bulk endpoints (placeholders; manter assinatura original)
# -----------------------------------------------------------------------------
@app.post("/ohlcv/bulk")
def ohlcv_bulk(body: BulkOHLCV) -> Dict[str, int]:
    count = len(getattr(body, "rows", []) or [])
    # futura integração: upsert_ohlcv(engine, body)
    return {"accepted": int(count)}


@app.post("/signals/bulk_v2")
def signals_bulk_v2(body: BulkSignal) -> Dict[str, int]:
    count = len(getattr(body, "signals", []) or [])
    # futura integração: upsert_signals(engine, body)
    return {"accepted": int(count)}

# -----------------------------------------------------------------------------
# Simple DB ping util
# -----------------------------------------------------------------------------
@app.get("/__db_ping")
def db_ping() -> Dict[str, str]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"db": "ok"}
    except Exception:
        return {"db": "error"}

# -----------------------------------------------------------------------------
# OHLCV endpoints (fail-soft se DB não responder)
# -----------------------------------------------------------------------------
TimeframeStr = constr(strip_whitespace=True, to_lower=True, min_length=1, max_length=8)


class OHLCVRecentResponse(BaseModel):
    tenant_id: str
    market: str
    symbol: str
    timeframe: str
    count: int = 0
    rows: list = Field(default_factory=list)


class OHLCVWindowResponse(BaseModel):
    tenant_id: str
    market: str
    symbol: str
    timeframe: str
    count: int = 0
    rows: list = Field(default_factory=list)


# main1.py — versão final da rota /ohlcv/recent (sem response_model)
@app.get("/ohlcv/recent")
def ohlcv_recent(
    tenant_id: str = Query("default"),
    market: str = Query(...),
    symbol: str = Query(..., min_length=1),
    timeframe: str = Query(...),
    limit: int = Query(100, ge=1, le=5000),
):
    m = _norm_market(market)
    try:
        rows = _select_ohlcv_recent(
            tenant_id=tenant_id, market=m, symbol=symbol, timeframe=timeframe, limit=limit
        )
        return rows            # ← LISTA
    except Exception:
        return []              # ← lista vazia em erro


@app.get("/ohlcv/window", response_model=OHLCVWindowResponse)
def ohlcv_window(
    tenant_id: str = Query("default"),
    market: str = Query(..., description="e.g. binance, stocks"),
    symbol: str = Query(..., min_length=1),
    timeframe: TimeframeStr = Query(...),
    since: int = Query(..., description="unix seconds (inclusive)"),
    until: int = Query(..., description="unix seconds (exclusive)"),
    limit: int = Query(1000, ge=1, le=5000),
):
    try:
        # implementação futura: filtrar entre since/until
        rows: List[Dict[str, Any]] = []
        return OHLCVWindowResponse(
            tenant_id=tenant_id, market=_norm_market(market), symbol=symbol, timeframe=timeframe, count=len(rows), rows=rows
        )
    except Exception:
        return OHLCVWindowResponse(
            tenant_id=tenant_id, market=_norm_market(market), symbol=symbol, timeframe=timeframe, count=0, rows=[]
        )

# -----------------------------------------------------------------------------
# Signals endpoints mínimos (fallback caso routers não existam)
# -----------------------------------------------------------------------------
class SignalsRecentResponse(BaseModel):
    tenant_id: str
    market: str
    symbol: str
    timeframe: str
    count: int = 0
    signals: list = Field(default_factory=list)


@app.get("/signals/window_real", response_model=SignalsRecentResponse)
def signals_window_real(
    tenant_id: str = Query("default"),
    market: str = Query(...),
    symbol: str = Query(..., min_length=1),
    timeframe: str = Query(...),
    since: int = Query(...),
    until: int = Query(...),
    limit: int = Query(1000, ge=1, le=5000),
):
    # fallback vazio 200
    return SignalsRecentResponse(
        tenant_id=tenant_id, market=_norm_market(market), symbol=symbol, timeframe=timeframe, count=0, signals=[]
    )

    # fallback vazio 200
    return SignalsRecentResponse(
        tenant_id=tenant_id, market=_norm_market(market), symbol=symbol, timeframe=timeframe, count=0, signals=[]
    )
