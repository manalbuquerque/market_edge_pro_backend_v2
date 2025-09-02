# routers_signals_mep_v2.py
from __future__ import annotations

"""
Signals router (full structure, service hooks preserved, engine-backed DB I/O).

Key points:
- Keeps original endpoints: GET /signals, GET /signals/recent, POST /signals/bulk
- Preserves service-layer indirection (imported if present), but
  DB calls default to stable inline implementations using `engine`.
- Avoids async DB driver issues by running synchronous SQLAlchemy
  work inside FastAPI's threadpool (`run_in_threadpool`).
- Safe JSON handling (payload->>'signal') with NULL-safe cast.

- NEW: GET /signals/window (filters by `since`/`until`).

Normalization rules:
  market -> lower()
  symbol -> upper()
  timeframe -> lower()

Signal payload schema (JSONB minimum):
  payload = {"signal": int in {-1,0,1}, ...optional metadata...}
"""

from typing import Any, Dict, List, Optional, Literal, Callable, Tuple, Union

import json
import logging
from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field, validator
from sqlalchemy import text

from starlette.concurrency import run_in_threadpool

# Use the sync Engine directly (stable in async endpoints when wrapped in threadpool)
from db_mep_v2 import engine  # must expose a sync SQLAlchemy Engine

# ------------------------------------------------------------------------------
# Optional service-layer integration
# ------------------------------------------------------------------------------

# We preserve the ability to call your service-layer functions if/when you restore
# them, but default to inline DB implementations to ensure stability.
USE_SERVICE_LAYER_DEFAULT = False  # flip to True when services are ready/desired

svc_read_signals: Optional[Callable[..., Any]] = None
svc_upsert_signals: Optional[Callable[..., Any]] = None
USE_SERVICE: bool = USE_SERVICE_LAYER_DEFAULT

try:
    # If your service module exists and you want to use it, set USE_SERVICE=True above.
    from services_storage_mep_v2 import (  # type: ignore
        read_signals as _svc_read_signals,
        upsert_signals as _svc_upsert_signals,
    )

    svc_read_signals = _svc_read_signals
    svc_upsert_signals = _svc_upsert_signals
except Exception:  # noqa: BLE001
    # Services unavailable; we will use inline DB logic.
    svc_read_signals = None
    svc_upsert_signals = None
    USE_SERVICE = False

# ------------------------------------------------------------------------------
# Router
# ------------------------------------------------------------------------------

router = APIRouter(prefix="/signals", tags=["signals"])

log = logging.getLogger("routers.signals")
if not log.handlers:
    # basic handler if not configured by app
    h = logging.StreamHandler()
    f = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    h.setFormatter(f)
    log.addHandler(h)
    log.setLevel(logging.INFO)

# ------------------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------------------

class SignalPoint(BaseModel):
    ts: int = Field(..., description="Timestamp in ms since epoch")
    signal: int = Field(..., ge=-1, le=1, description="-1, 0, or 1")


class BulkSignalsIn(BaseModel):
    tenant_id: str = Field(default="default")
    market: str
    symbol: str
    timeframe: str
    mode: Literal["replace", "append"] = "replace"
    signals: List[SignalPoint]

    @validator("market")
    def market_norm(cls, v: str) -> str:  # noqa: D401
        return (v or "").strip().lower()

    @validator("symbol")
    def symbol_norm(cls, v: str) -> str:  # noqa: D401
        return (v or "").strip().upper()

    @validator("timeframe")
    def tf_norm(cls, v: str) -> str:  # noqa: D401
        return (v or "").strip().lower()

# ------------------------------------------------------------------------------
# Helper utilities (kept for structure; some not strictly needed but preserved)
# ------------------------------------------------------------------------------

def _safe_int(v: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(v)
    except Exception:  # noqa: BLE001
        return default


def _truncate_msg(msg: str, limit: int = 400) -> str:
    if len(msg) <= limit:
        return msg
    return msg[:limit - 3] + "..."


def _http500(msg: str) -> HTTPException:
    return HTTPException(status_code=500, detail=_truncate_msg(msg))


def _normalize_keys(
    tenant_id: str, market: str, symbol: str, timeframe: str
) -> Tuple[str, str, str, str]:
    return (
        (tenant_id or "default"),
        (market or "").lower(),
        (symbol or "").upper(),
        (timeframe or "").lower(),
    )


def _rows_to_dicts(rows: List[Any]) -> List[Dict[str, Any]]:
    return [dict(r) for r in rows]


# ------------------------------------------------------------------------------
# Inline DB implementations (engine + threadpool)
# ------------------------------------------------------------------------------

def _build_read_sql(
    has_since: bool, has_until: bool
) -> Tuple[str, List[str]]:
    clauses = [
        "tenant_id = :tenant_id",
        "market = :market",
        "symbol = :symbol",
        "timeframe = :timeframe",
    ]
    if has_since:
        clauses.append("ts >= :since")
    if has_until:
        clauses.append("ts < :until")
    sql = f"""
        SELECT
            ts,
            NULLIF(payload->>'signal','')::int AS signal
        FROM signals
        WHERE {' AND '.join(clauses)}
        ORDER BY ts DESC
        LIMIT :limit
    """
    return sql, clauses


def _exec_read_signals_sync(
    tenant_id: str,
    market: str,
    symbol: str,
    timeframe: str,
    since: Optional[int],
    until: Optional[int],
    limit: int,
) -> List[Dict[str, Any]]:
    sql, _ = _build_read_sql(has_since=since is not None, has_until=until is not None)
    params: Dict[str, Any] = dict(
        tenant_id=tenant_id,
        market=market,
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
    )
    if since is not None:
        params["since"] = since
    if until is not None:
        params["until"] = until

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
        return _rows_to_dicts(rows)


async def _read_signals_inline(
    tenant_id: str,
    market: str,
    symbol: str,
    timeframe: str,
    since: Optional[int],
    until: Optional[int],
    limit: int,
) -> List[Dict[str, Any]]:
    # Run sync DB call in threadpool to avoid blocking the event loop
    return await run_in_threadpool(
        _exec_read_signals_sync,
        tenant_id, market, symbol, timeframe, since, until, limit
    )


def _exec_delete_scope_sync(
    tenant_id: str, market: str, symbol: str, timeframe: str
) -> int:
    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                DELETE FROM signals
                WHERE tenant_id=:tenant_id AND market=:market
                  AND symbol=:symbol AND timeframe=:timeframe
                """
            ),
            dict(tenant_id=tenant_id, market=market, symbol=symbol, timeframe=timeframe),
        )
        return int(getattr(res, "rowcount", 0) or 0)


def _exec_insert_signals_sync(
    tenant_id: str,
    market: str,
    symbol: str,
    timeframe: str,
    rows: List[Dict[str, Any]],
    on_conflict_do_nothing: bool = True,
) -> int:
    # We keep a simple executemany loop for readability and stability.
    sql = text(
        """
        INSERT INTO signals (id, tenant_id, market, symbol, timeframe, payload, ts)
        VALUES (gen_random_uuid(), :tenant_id, :market, :symbol, :timeframe,
                jsonb_build_object('signal', :signal), :ts)
        """ + (" ON CONFLICT DO NOTHING" if on_conflict_do_nothing else "")
    )

    insert_params = []
    for r in rows:
        insert_params.append(
            dict(
                tenant_id=tenant_id,
                market=market,
                symbol=symbol,
                timeframe=timeframe,
                ts=int(r["ts"]),
                signal=int(r["signal"]),
            )
        )

    with engine.begin() as conn:
        res = conn.execute(sql, insert_params)  # type: ignore[arg-type]
        # SQLAlchemy executemany returns rowcount (may be -1 with some drivers)
        rc = getattr(res, "rowcount", None)
        if not isinstance(rc, int) or rc < 0:
            # Fall back to len(rows) if driver doesn't report
            rc = len(insert_params)
        return int(rc)


async def _upsert_signals_inline(
    tenant_id: str,
    market: str,
    symbol: str,
    timeframe: str,
    mode: Literal["replace", "append"],
    signals: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if not signals:
        return {"inserted": 0, "replaced": False}

    # Optional delete when replacing
    replaced = False
    if mode == "replace":
        deleted = await run_in_threadpool(
            _exec_delete_scope_sync, tenant_id, market, symbol, timeframe
        )
        log.info(
            "signals.replace scope deleted=%s tenant=%s market=%s symbol=%s tf=%s",
            deleted, tenant_id, market, symbol, timeframe
        )
        replaced = True

    inserted = await run_in_threadpool(
        _exec_insert_signals_sync,
        tenant_id, market, symbol, timeframe, signals, True
    )

    return {"inserted": int(inserted), "replaced": replaced}

# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------

@router.get("/")
@router.get("")  # support both /signals and /signals/
async def get_signals(
    tenant_id: str = Query("default"),
    market: str = Query(...),
    symbol: str = Query(...),
    timeframe: str = Query(...),
    since: Optional[int] = Query(None, description="ms since epoch (inclusive)"),
    until: Optional[int] = Query(None, description="ms since epoch (exclusive)"),
    limit: int = Query(500, ge=1, le=5000),
):
    """
    List signals from DB. Returns [] if none.
    Response:
    {
      tenant_id, market, symbol, timeframe,
      count, signals: [{ts, signal}]
    }
    """
    tenant_id, market_l, symbol_u, timeframe_l = _normalize_keys(
        tenant_id, market, symbol, timeframe
    )

    try:
        if USE_SERVICE and svc_read_signals:
            # Service signature parity: pass same args
            rows = await run_in_threadpool(
                svc_read_signals,
                session=None,  # kept for signature compatibility, ignored here
                tenant_id=tenant_id,
                market=market_l,
                symbol=symbol_u,
                timeframe=timeframe_l,
                since=since,
                until=until,
                limit=limit,
            )
        else:
            rows = await _read_signals_inline(
                tenant_id, market_l, symbol_u, timeframe_l, since, until, limit
            )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log.exception("GET /signals failed")
        raise _http500(str(e))

    return {
        "tenant_id": tenant_id,
        "market": market_l,
        "symbol": symbol_u,
        "timeframe": timeframe_l,
        "count": len(rows),
        "signals": rows,
    }


@router.get("/recent")
async def get_signals_recent(
    tenant_id: str = Query("default"),
    market: str = Query(...),
    symbol: str = Query(...),
    timeframe: str = Query(...),
    limit: int = Query(500, ge=1, le=5000),
):
    """
    Convenience alias for the latest N signals. Uses the same implementation
    as GET /signals without since/until filters.
    """
    return await get_signals(
        tenant_id=tenant_id,
        market=market,
        symbol=symbol,
        timeframe=timeframe,
        since=None,
        until=None,
        limit=limit,
    )

@router.get("/window")
async def get_signals_window(
    tenant_id: str = Query("default"),
    market: str = Query(...),
    symbol: str = Query(...),
    timeframe: str = Query(...),
    since: Optional[int] = Query(None, description="ms since epoch (inclusive)"),
    until: Optional[int] = Query(None, description="ms since epoch (exclusive)"),
    limit: int = Query(500, ge=1, le=5000),
):
    '''
    Windowed signal query. Same as GET /signals but emphasizes use of `since`/`until`.
    Response: {tenant_id, market, symbol, timeframe, count, signals: [{ts, signal}]}
    '''
    tenant_id, market_l, symbol_u, timeframe_l = _normalize_keys(
        tenant_id, market, symbol, timeframe
    )
    try:
        rows = await _read_signals_inline(
            tenant_id, market_l, symbol_u, timeframe_l, since, until, limit
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log.exception("GET /signals/window failed")
        raise _http500(str(e))

    return {
        "tenant_id": tenant_id,
        "market": market_l,
        "symbol": symbol_u,
        "timeframe": timeframe_l,
        "count": len(rows),
        "signals": rows,
    }


@router.post("/bulk")
async def upsert_signals_bulk(
    payload: BulkSignalsIn = Body(...),
):
    """
    Insert/replace signals for a (tenant, market, symbol, timeframe).
    - mode='replace': delete prior then insert provided set
    - mode='append' : insert provided set (on conflict do nothing)

    Body example:
    {
      "tenant_id": "t1",
      "market": "CRYPTO",
      "symbol": "BTCUSDT",
      "timeframe": "1m",
      "mode": "append",
      "signals": [{"ts": 1700000120, "signal": 1}, {"ts": 1700000180, "signal": 0}]
    }
    """
    tenant_id, market_l, symbol_u, timeframe_l = _normalize_keys(
        payload.tenant_id, payload.market, payload.symbol, payload.timeframe
    )

    data: List[Dict[str, Any]] = []
    for s in payload.signals:
        # Be strict and safe here
        tsi = _safe_int(s.ts)
        sigi = _safe_int(s.signal)
        if tsi is None or sigi is None:
            raise HTTPException(status_code=422, detail="Invalid ts/signal")
        data.append({"ts": tsi, "signal": sigi})

    try:
        if USE_SERVICE and svc_upsert_signals:
            result = await run_in_threadpool(
                svc_upsert_signals,
                session=None,  # preserved for signature compatibility
                tenant_id=tenant_id,
                market=market_l,
                symbol=symbol_u,
                timeframe=timeframe_l,
                mode=payload.mode,
                signals=data,
            )
        else:
            result = await _upsert_signals_inline(
                tenant_id=tenant_id,
                market=market_l,
                symbol=symbol_u,
                timeframe=timeframe_l,
                mode=payload.mode,
                signals=data,
            )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log.exception("POST /signals/bulk failed")
        raise _http500(str(e))

    return {
        "tenant_id": tenant_id,
        "market": market_l,
        "symbol": symbol_u,
        "timeframe": timeframe_l,
        "mode": payload.mode,
        "inserted": int(result.get("inserted", 0)),
        "replaced": bool(result.get("replaced", False)),
    }

# ------------------------------------------------------------------------------
# (Optional) future expansion points – kept to preserve line count/structure
# ------------------------------------------------------------------------------

def _example_future_transform(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Placeholder for future business logic transformations on payload before insert.
    Currently no-op; kept to preserve structure and make future diffs smaller.
    """
    # Example: enrich with computed features, normalize fields, etc.
    return payload


def _validate_signal_window(points: List[SignalPoint]) -> None:
    """
    Placeholder for future validation across the signal set (monotonic ts, gaps).
    Currently no-op; kept for structure.
    """
    # Example:
    # ts_prev = None
    # for p in points:
    #     if ts_prev is not None and p.ts <= ts_prev:
    #         raise HTTPException(422, "Non-monotonic timestamps")
    #     ts_prev = p.ts
    return


def _log_audit_event(
    action: str,
    tenant_id: str,
    market: str,
    symbol: str,
    timeframe: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Placeholder for audit logging hook; kept for structure.
    """
    try:
        log.debug(
            "AUDIT action=%s tenant=%s market=%s symbol=%s tf=%s meta=%s",
            action, tenant_id, market, symbol, timeframe, json.dumps(metadata or {}),
        )
    except Exception:  # noqa: BLE001
        pass


# end of file

