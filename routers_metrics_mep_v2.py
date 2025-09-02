# routers_metrics_mep_v2.py
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from db_mep_v2 import get_session_optional
from services_storage_mep_v2 import read_ohlcv
from services_market_mep_v2 import fetch_binance_ohlcv

router = APIRouter(tags=["metrics-v2"])

# ---------- helpers ----------
def _to_df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["ts","open","high","low","close","volume"])
    df = pd.DataFrame(rows)
    for c in ["open","high","low","close","volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["ts"] = pd.to_numeric(df["ts"], errors="coerce")
    df = df.dropna(subset=["ts","close"]).sort_values("ts").reset_index(drop=True)
    return df

async def _load_df(
    session: Optional[AsyncSession],
    market: str,
    symbol: str,
    timeframe: str,
    lookback: int
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    if session is not None:
        rows = await read_ohlcv(session, "default", market, symbol, timeframe, None, None)
    if not rows:
        if market.lower() != "binance":
            raise HTTPException(status_code=400, detail="Only 'binance' supported for live fetch.")
        rows = await fetch_binance_ohlcv(symbol, timeframe, None, None)
    df = _to_df(rows)
    if lookback and lookback > 0 and not df.empty:
        df = df.tail(int(lookback))
    return df

async def _load_signals(
    session: Optional[AsyncSession],
    tenant_id: str,
    market: str,
    symbol: str,
    timeframe: str,
) -> List[Dict[str, int]]:
    if session is None:
        return []
    q = text("""
        SELECT (payload->>'ts')::bigint AS ts, (payload->>'signal')::int AS signal
        FROM signals
        WHERE tenant_id=:tenant_id AND market=:market AND symbol=:symbol AND timeframe=:timeframe
        ORDER BY (payload->>'ts')::bigint ASC
    """)
    res = await session.execute(q, dict(tenant_id=tenant_id, market=market, symbol=symbol, timeframe=timeframe))
    return [{"ts": int(r[0]), "signal": int(r[1])} for r in res.fetchall()]

def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()

def _fallback_signals_ema20(df: pd.DataFrame) -> List[Dict[str, int]]:
    if df.empty:
        return []
    ema_fast = _ema(df["close"], span=12)
    ema_slow = _ema(df["close"], span=26)
    sig = (ema_fast > ema_slow).astype(int) - (ema_fast < ema_slow).astype(int)
    return [{"ts": int(ts), "signal": int(s)} for ts, s in zip(df["ts"], sig.fillna(0))]

def _align_signals(df: pd.DataFrame, signals: List[Dict[str,int]]) -> pd.DataFrame:
    if df.empty or not signals:
        return pd.DataFrame(columns=["ts","signal"])
    s = pd.DataFrame(signals).dropna().astype({"ts":"int64","signal":"int64"})
    return s.sort_values("ts")

def _future_return(df: pd.DataFrame, horizon_bars: int) -> pd.Series:
    c = df["close"].astype(float)
    fwd = c.shift(-horizon_bars)
    return (fwd / c) - 1.0

def _compute_accuracy(df: pd.DataFrame, sig_df: pd.DataFrame, horizon_bars: int) -> Tuple[float, int]:
    merged = pd.merge(sig_df, df[["ts","close"]], on="ts", how="inner")
    if merged.empty:
        return 0.0, 0
    merged["fwd_ret"] = _future_return(df, horizon_bars).reindex(merged.index)
    merged = merged.dropna(subset=["fwd_ret"])
    if merged.empty:
        return 0.0, 0
    correct = (merged["signal"] * merged["fwd_ret"] > 0).sum()
    n = len(merged)
    return (float(correct) / float(n) if n else 0.0), n

def _simulate_pnl(df: pd.DataFrame, sig_df: pd.DataFrame, fee_bps: float, slippage_bps: float) -> Tuple[float, int, float]:
    if df.empty or sig_df.empty:
        return 0.0, 0, 0.0
    merged = pd.merge(sig_df, df[["ts","open","close"]], on="ts", how="inner").sort_values("ts").reset_index(drop=True)
    if merged.empty:
        return 0.0, 0, 0.0
    costs = (fee_bps + slippage_bps) / 10000.0
    pnl = 0.0
    rets: List[float] = []
    n_trades = 0
    prev_sig = 0
    for i in range(len(merged)-1):
        s = int(merged.loc[i, "signal"])
        nxt_open = df.loc[df["ts"] == merged.loc[i+1, "ts"], "open"]
        cur_open = df.loc[df["ts"] == merged.loc[i, "ts"], "open"]
        if nxt_open.empty or cur_open.empty:
            continue
        n_trades += 1 if s != prev_sig and s != 0 else 0
        prev_sig = s
        r = (float(nxt_open.values[0]) / float(cur_open.values[0])) - 1.0
        trade_ret = s * r - 2.0 * costs
        pnl += trade_ret
        rets.append(trade_ret)
    if rets:
        s = pd.Series(rets)
        sharpe = float(s.mean()) / float(s.std(ddof=1)) if len(s) > 1 and s.std(ddof=1) > 0 else 0.0
    else:
        sharpe = 0.0
    return pnl, n_trades, sharpe

async def _persist_accuracy(session: Optional[AsyncSession], tenant_id: str, market: str, symbol: str,
                            timeframe: str, lookback: int, horizon_bars: int, accuracy: float, source: str) -> Optional[str]:
    if session is None:
        return None
    stmt = text("""
        INSERT INTO accuracy_metrics
            (id, tenant_id, market, symbol, timeframe, lookback, horizon_bars, accuracy, source, created_at)
        VALUES (:id, :tenant_id, :market, :symbol, :timeframe, :lookback, :horizon_bars, :accuracy, :source, NOW())
        ON CONFLICT (id) DO NOTHING
    """)
    _id = str(uuid.uuid4())
    await session.execute(stmt, dict(
        id=_id, tenant_id=tenant_id, market=market, symbol=symbol, timeframe=timeframe,
        lookback=lookback, horizon_bars=horizon_bars, accuracy=accuracy, source=source
    ))
    return _id

async def _persist_pnl(session: Optional[AsyncSession], tenant_id: str, market: str, symbol: str, timeframe: str,
                       lookback: int, fee_bps: float, slippage_bps: float, total_return: float, n_trades: int,
                       sharpe: float, source: str) -> Optional[str]:
    if session is None:
        return None
    stmt = text("""
        INSERT INTO simulated_pnl
            (id, tenant_id, market, symbol, timeframe, lookback, fee_bps, slippage_bps, total_return, n_trades, sharpe, source, created_at)
        VALUES (:id, :tenant_id, :market, :symbol, :timeframe, :lookback, :fee_bps, :slippage_bps, :total_return, :n_trades, :sharpe, :source, NOW())
        ON CONFLICT (id) DO NOTHING
    """)
    _id = str(uuid.uuid4())
    await session.execute(stmt, dict(
        id=_id, tenant_id=tenant_id, market=market, symbol=symbol, timeframe=timeframe,
        lookback=lookback, fee_bps=fee_bps, slippage_bps=slippage_bps,
        total_return=total_return, n_trades=n_trades, sharpe=sharpe, source=source
    ))
    return _id

# ---------- endpoints ----------
@router.post("/metrics/accuracy")
async def metrics_accuracy(
    payload: Dict[str, Any] = Body(...),
    session: Optional[AsyncSession] = Depends(get_session_optional),
):
    market = (payload.get("market") or "binance").lower()
    symbol = (payload.get("symbol") or "BTCUSDT").upper()
    timeframe = payload.get("timeframe") or "1h"
    lookback = int(payload.get("lookback", 1000))
    horizon_bars = int(payload.get("horizon_bars", 24))
    persist = bool(payload.get("persist", True))
    fallback_if_missing = bool(payload.get("fallback_if_missing", True))
    tenant_id = payload.get("tenant_id", "default")

    df = await _load_df(session, market, symbol, timeframe, lookback)
    if df.empty:
        raise HTTPException(status_code=404, detail="No OHLCV data available.")

    sigs = await _load_signals(session, tenant_id, market, symbol, timeframe)
    source = "db" if sigs else "fallback_ema20" if fallback_if_missing else "none"
    if not sigs and not fallback_if_missing:
        raise HTTPException(status_code=404, detail="No signals found for this key.")
    if not sigs and fallback_if_missing:
        sigs = _fallback_signals_ema20(df)

    sig_df = _align_signals(df, sigs)
    acc, n = _compute_accuracy(df, sig_df, horizon_bars)

    persisted_id: Optional[str] = None
    if persist:
        persisted_id = await _persist_accuracy(session, tenant_id, market, symbol, timeframe, lookback, horizon_bars, acc, source)
        if session is not None:
            await session.commit()

    return {
        "tenant_id": tenant_id, "market": market, "symbol": symbol, "timeframe": timeframe,
        "lookback": lookback, "horizon_bars": horizon_bars,
        "source": source, "accuracy": round(acc, 6), "n_signals": n,
        "persisted_id": persisted_id,
    }

@router.post("/metrics/pnl")
async def metrics_pnl(
    payload: Dict[str, Any] = Body(...),
    session: Optional[AsyncSession] = Depends(get_session_optional),
):
    market = (payload.get("market") or "binance").lower()
    symbol = (payload.get("symbol") or "BTCUSDT").upper()
    timeframe = payload.get("timeframe") or "1h"
    lookback = int(payload.get("lookback", 1000))
    fee_bps = float(payload.get("fee_bps", 10))
    slippage_bps = float(payload.get("slippage_bps", 5))
    persist = bool(payload.get("persist", True))
    fallback_if_missing = bool(payload.get("fallback_if_missing", True))
    tenant_id = payload.get("tenant_id", "default")

    df = await _load_df(session, market, symbol, timeframe, lookback)
    if df.empty:
        raise HTTPException(status_code=404, detail="No OHLCV data available.")

    sigs = await _load_signals(session, tenant_id, market, symbol, timeframe)
    source = "db" if sigs else "fallback_ema20" if fallback_if_missing else "none"
    if not sigs and not fallback_if_missing:
        raise HTTPException(status_code=404, detail="No signals found for this key.")
    if not sigs and fallback_if_missing:
        sigs = _fallback_signals_ema20(df)

    sig_df = _align_signals(df, sigs)
    total_return, n_trades, sharpe = _simulate_pnl(df, sig_df, fee_bps, slippage_bps)

    persisted_id: Optional[str] = None
    if persist:
        persisted_id = await _persist_pnl(session, tenant_id, market, symbol, timeframe, lookback,
                                          fee_bps, slippage_bps, total_return, n_trades, sharpe, source)
        if session is not None:
            await session.commit()

    return {
        "tenant_id": tenant_id, "market": market, "symbol": symbol, "timeframe": timeframe, "lookback": lookback,
        "fee_bps": fee_bps, "slippage_bps": slippage_bps,
        "source": source, "total_return": round(float(total_return), 6),
        "n_trades": int(n_trades), "sharpe_like": round(float(sharpe), 6),
        "persisted_id": persisted_id,
    }
