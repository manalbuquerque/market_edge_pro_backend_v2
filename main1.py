# main1.py
from __future__ import annotations

import os, secrets, importlib
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRouter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Result

from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Gauge, generate_latest

# Optional middlewares you already have in the repo
from middleware_observability import ObservabilityMiddleware
from middleware_ratelimit import RateLimitMiddleware

# -----------------------------------------------------------------------------
# App & config
# -----------------------------------------------------------------------------
app = FastAPI(title="Market Edge Pro Backend", version="0.2.0")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@db:5432/market_edge",
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

APIKEY_ENABLED = os.getenv("APIKEY_ENABLED", "1").lower() not in ("0", "false", "")
STATIC_KEYS = {k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()}
PUBLIC = {
    p.strip()
    for p in os.getenv(
        "APIKEY_PUBLIC",
        "/docs,/openapi.json,/health,/healthz,/ready,/readyz,/metrics,/stripe/webhook",
    ).split(",")
    if p.strip()
}

def _is_public(path: str) -> bool:
    return path in PUBLIC or path.startswith("/docs") or path.startswith("/openapi")

def _db_has_active_key(k: str) -> bool:
    try:
        with engine.connect() as c:
            return bool(
                c.execute(
                    text("SELECT 1 FROM api_keys WHERE key=:k AND active=true LIMIT 1"),
                    {"k": k},
                ).first()
            )
    except Exception:
        # table might not exist yet
        return False

@app.middleware("http")
async def apikey_mw(request: Request, call_next):
    if not APIKEY_ENABLED or _is_public(request.url.path):
        return await call_next(request)

    key = request.headers.get("x-api-key") or request.headers.get("X-API-Key")
    if not key:
        return JSONResponse(status_code=401, content={"detail": "invalid or missing API key"})
    if key in STATIC_KEYS or _db_has_active_key(key):
        return await call_next(request)
    return JSONResponse(status_code=401, content={"detail": "invalid or missing API key"})

# -----------------------------------------------------------------------------
# CORS (dev-open; tighten in prod)
# -----------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Stripe webhook (idempotent; correct uniques; no key rotation)
# -----------------------------------------------------------------------------
@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.json()
    evt_type = payload.get("type")
    obj = (payload.get("data") or {}).get("object") or {}

    if evt_type != "checkout.session.completed":
        return {"ok": True, "ignored": True}

    customer = (obj.get("customer") or "").strip()
    sub_id = (obj.get("subscription") or "").strip()
    email = ((obj.get("customer_details") or {}).get("email") or "").strip().lower()
    cpe = int(obj.get("current_period_end") or 0)

    lines = (obj.get("lines") or {}).get("data") or []
    plan = ((((lines[0] or {}).get("plan") or {}).get("id")) or "pro").strip() if lines else "pro"

    if not (email and sub_id):
        return JSONResponse(status_code=400, content={"detail": "missing email/subscription"})

    with engine.begin() as c:
        # Ensure tables exist (safe if migrations were skipped)
        c.execute(text("""
        CREATE TABLE IF NOT EXISTS subscriptions (
          id SERIAL PRIMARY KEY,
          customer_id TEXT NOT NULL,
          subscription_id TEXT NOT NULL,
          email TEXT NOT NULL,
          plan TEXT NOT NULL DEFAULT 'pro',
          status TEXT NOT NULL DEFAULT 'active',
          current_period_end BIGINT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """))
        c.execute(text("""
        CREATE TABLE IF NOT EXISTS api_keys (
          id SERIAL PRIMARY KEY,
          user_email TEXT NOT NULL,
          plan TEXT NOT NULL DEFAULT 'pro',
          key TEXT NOT NULL UNIQUE,
          active BOOLEAN NOT NULL DEFAULT TRUE,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """))

        # Correct unique constraints (once)
        c.execute(text("""
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='uq_subscriptions_subscription_id') THEN
            ALTER TABLE subscriptions ADD CONSTRAINT uq_subscriptions_subscription_id UNIQUE (subscription_id);
          END IF;
        END$$;
        """))
        c.execute(text("""
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='uq_api_keys_user_plan') THEN
            ALTER TABLE api_keys ADD CONSTRAINT uq_api_keys_user_plan UNIQUE (user_email, plan);
          END IF;
        END$$;
        """))
        c.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_api_keys_key ON api_keys(key);"))

        # Upsert subscription by subscription_id (idempotent)
        c.execute(text("""
            INSERT INTO subscriptions (customer_id, subscription_id, email, plan, status, current_period_end)
            VALUES (:cust, :sub, :email, :plan, 'active', :cpe)
            ON CONFLICT (subscription_id) DO UPDATE
               SET customer_id = EXCLUDED.customer_id,
                   email       = EXCLUDED.email,
                   plan        = EXCLUDED.plan,
                   status      = 'active',
                   current_period_end = EXCLUDED.current_period_end;
        """), {"cust": customer, "sub": sub_id, "email": email, "plan": plan, "cpe": cpe})

        # One API key per (email, plan) — do NOT rotate if it already exists
        row = c.execute(text("""
            UPDATE api_keys SET active=TRUE
             WHERE user_email=:email AND plan=:plan
         RETURNING key;
        """), {"email": email, "plan": plan}).fetchone()

        if row:
            api_key = row[0]
        else:
            candidate = secrets.token_hex(32)
            ins = c.execute(text("""
                INSERT INTO api_keys (user_email, plan, key, active)
                VALUES (:email, :plan, :key, TRUE)
                ON CONFLICT (user_email, plan) DO NOTHING
             RETURNING key;
            """), {"email": email, "plan": plan, "key": candidate}).fetchone()

            if ins:
                api_key = ins[0]
            else:
                api_key = c.execute(text("""
                    SELECT key FROM api_keys WHERE user_email=:email AND plan=:plan;
                """), {"email": email, "plan": plan}).scalar_one()

    return {"ok": True, "activated": True, "api_key": api_key}
# -----------------------------------------------------------------------------
# Health / Ready / Metrics
# -----------------------------------------------------------------------------
def _table_exists(conn, name: str) -> bool:
    return name in set(inspect(conn).get_table_names())

@app.get("/health")
@app.get("/healthz")
def health():
    return {"status": "ok"}

@app.get("/ready")
@app.get("/readyz")
def ready():
    missing: List[str] = []
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            for t in ("ohlcv", "signals"):
                if not _table_exists(conn, t):
                    missing.append(t)
    except Exception:
        missing = ["db_or_tables_check_failed"]
    return {"ready": True, "status": "ready", "missing": missing}

# process_max_fds shim (Windows)
try:
    _fds = Gauge("process_max_fds", "Maximum number of open file descriptors (shim).")
    _fds.set(float(os.getenv("PROCESS_MAX_FDS", "1048576")))
except Exception:
    pass

@app.get("/metrics")
def metrics():
    try:
        data = generate_latest(REGISTRY)
    except Exception:
        data = b""
    extra = (
        b"# HELP process_max_fds Maximum number of open file descriptors.\n"
        b"# TYPE process_max_fds gauge\n"
        + f"process_max_fds {float(os.getenv('PROCESS_MAX_FDS','1048576'))}\n".encode()
    )
    return Response(content=data + extra, media_type=CONTENT_TYPE_LATEST, status_code=200)

# -----------------------------------------------------------------------------
# Minimal data endpoints
# -----------------------------------------------------------------------------
def _norm(s: str) -> str:
    return (s or "").strip().lower()

def _select_ohlcv_recent(
    tenant_id: str, market: str, symbol: str, timeframe: str, limit: int
) -> List[Dict[str, Any]]:
    sql = text("""
        SELECT tenant_id, market, symbol, timeframe, ts, open, high, low, close, volume
        FROM ohlcv
        WHERE tenant_id=:tenant_id AND market=:market AND symbol=:symbol AND timeframe=:timeframe
        ORDER BY ts DESC
        LIMIT :limit""")
    with engine.connect() as conn:
        if not _table_exists(conn, "ohlcv"):
            return []
        res: Result = conn.execute(sql, dict(
            tenant_id=tenant_id, market=market, symbol=symbol, timeframe=timeframe, limit=int(limit)
        ))
        return [dict(
            tenant_id=r[0], market=r[1], symbol=r[2], timeframe=r[3], ts=int(r[4]),
            open=float(r[5]), high=float(r[6]), low=float(r[7]), close=float(r[8]), volume=float(r[9])
        ) for r in res.fetchall()]

@app.get("/ohlcv/recent")
def ohlcv_recent(
    tenant_id: str = Query("t1"),
    market: str = Query(...),
    symbol: str = Query(..., min_length=1),
    timeframe: str = Query(...),
    limit: int = Query(100, ge=1, le=5000),
):
    try:
        return _select_ohlcv_recent(tenant_id, _norm(market), symbol, timeframe, limit)
    except Exception:
        return []

# -----------------------------------------------------------------------------
# Include optional routers if present
# -----------------------------------------------------------------------------
def _include_router(module_name: str) -> None:
    try:
        mod = importlib.import_module(module_name)
    except Exception:
        return
    r: Optional[APIRouter] = getattr(mod, "router", None)
    if isinstance(r, APIRouter):
        app.include_router(r)

for mod in (
    "routers_data_mep_v2",
    "routers_signals_mep_v2",
    "routers_metrics_mep_v2",
    "routers_backtests_mep_v2",
    "routers_screener_mep_v2",
):
    _include_router(mod)
# -----------------------------------------------------------------------------
# Fail-soft middleware (outermost)
# -----------------------------------------------------------------------------
class FailSoftMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        p = (request.url.path or "/").rstrip("/")
        try:
            return await call_next(request)
        except Exception:
            if p.startswith("/ohlcv/"):
                q = request.query_params
                return JSONResponse(
                    {
                        "tenant_id": q.get("tenant_id", "t1"),
                        "market": _norm(q.get("market") or ""),
                        "symbol": q.get("symbol", ""),
                        "timeframe": q.get("timeframe", ""),
                        "count": 0,
                        "rows": [],
                    },
                    status_code=200,
                )
            return JSONResponse({"error": "temporary failure"}, status_code=200)

# middleware order: last added runs first
app.add_middleware(ObservabilityMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(FailSoftMiddleware)

