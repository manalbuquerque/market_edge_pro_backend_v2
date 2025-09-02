
from __future__ import annotations
import uuid
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models_mep_v2 import AccuracyMetric, SimulatedPnL, Signal
from backtesting_mep_v2 import event_backtest

# -----------------------------
# Helpers
# -----------------------------
def _to_df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["ts","open","high","low","close","volume"])
    df = pd.DataFrame(rows)
    # normalize columns
    expected = ["ts","open","high","low","close","volume"]
    for col in expected:
        if col not in df.columns:
            df[col] = np.nan
    df = df[expected].copy()
    df["ts"] = df["ts"].astype("int64")
    df[["open","high","low","close","volume"]] = df[["open","high","low","close","volume"]].astype("float64")
    return df.sort_values("ts").reset_index(drop=True)

async def load_signals_series(session: Optional[AsyncSession], tenant_id: str, market: str, symbol: str, timeframe: str) -> Optional[pd.Series]:
    if session is None:
        return None
    q = select(Signal).where(
        Signal.tenant_id==tenant_id,
        Signal.market==market,
        Signal.symbol==symbol,
        Signal.timeframe==timeframe
    )
    res = await session.execute(q)
    rows = res.scalars().all()
    if not rows:
        return None
    # Expect each row.payload to contain {"ts":..., "signal": -1|0|1}
    ts = []
    sig = []
    for r in rows:
        p = r.payload or {}
        if "ts" in p and "signal" in p:
            ts.append(int(p["ts"]))
            sig.append(int(p["signal"]))
    if not ts:
        return None
    return pd.Series(sig, index=pd.Index(ts, name="ts"), name="signal").sort_index()

def compute_accuracy(df: pd.DataFrame, sig: pd.Series, horizon_bars: int=24) -> Dict[str, Any]:
    """
    Assunção: sig in {-1,0,1}. Contam-se apenas sinais != 0.
    Regra de acerto: sign(close[t+h]-close[t]) == sig[t].
    """
    # align by ts
    base = df.set_index("ts")[["close"]].copy()
    s = sig.loc[sig.index.intersection(base.index)]
    if s.empty:
        return {"samples": 0, "hits": 0, "accuracy": 0.0, "by_side": {"long": {"n":0,"hits":0}, "short":{"n":0,"hits":0}}}
    base = base.join(s.rename("signal"), how="left")
    base["fwd_close"] = base["close"].shift(-horizon_bars)
    base["ret"] = (base["fwd_close"] - base["close"]) / base["close"]
    mask = base["signal"] != 0
    mask &= base["fwd_close"].notna()
    sub = base.loc[mask]
    if sub.empty:
        return {"samples": 0, "hits": 0, "accuracy": 0.0, "by_side": {"long": {"n":0,"hits":0}, "short":{"n":0,"hits":0}}}
    # hit if sign matches
    pred = np.sign(sub["ret"].to_numpy())
    truth = sub["signal"].to_numpy()
    hits = (pred == truth).sum()
    samples = len(sub)
    # breakdown
    long_mask = truth == 1
    short_mask = truth == -1
    long_hits = (pred[long_mask] == 1).sum()
    short_hits = (pred[short_mask] == -1).sum()
    acc = float(hits) / float(samples) if samples else 0.0
    return {
        "samples": int(samples),
        "hits": int(hits),
        "accuracy": float(acc),
        "by_side": {
            "long": {"n": int(long_mask.sum()), "hits": int(long_hits)},
            "short": {"n": int(short_mask.sum()), "hits": int(short_hits)},
        },
    }

def compute_pnl(df: pd.DataFrame, sig: pd.Series, fee_bps: float=10.0, slippage_bps: float=5.0) -> Dict[str, Any]:
    base = df.copy()
    # align
    s = sig.reindex(base["ts"].to_numpy(), fill_value=0)
    base["signal"] = s.to_numpy()
    pnl, dd, trades, eq = event_backtest(base, signal_col="signal", fee_bps=fee_bps, slippage_bps=slippage_bps)
    return {
        "total_pnl": float(pnl),
        "max_drawdown": float(dd),
        "n_trades": int(len(trades)),
        "equity_curve": [float(x) for x in eq],
    }

async def upsert_accuracy(session: Optional[AsyncSession], key: Dict[str, Any], res: Dict[str, Any]) -> Optional[str]:
    if session is None:
        return None
    stmt = pg_insert(AccuracyMetric).values(
        id=str(uuid.uuid4()),
        tenant_id=key["tenant_id"], market=key["market"], symbol=key["symbol"], timeframe=key["timeframe"],
        horizon_bars=key["horizon_bars"],
        sample_count=res["samples"], hit_count=res["hits"], accuracy=res["accuracy"], details=res
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["tenant_id","market","symbol","timeframe","horizon_bars"],
        set_={
            "sample_count": stmt.excluded.sample_count,
            "hit_count": stmt.excluded.hit_count,
            "accuracy": stmt.excluded.accuracy,
            "details": stmt.excluded.details,
        }
    ).returning(AccuracyMetric.id)
    row = await session.execute(stmt)
    rid = row.scalar_one()
    await session.commit()
    return rid

async def upsert_pnl(session: Optional[AsyncSession], key: Dict[str, Any], res: Dict[str, Any]) -> Optional[str]:
    if session is None:
        return None
    stmt = pg_insert(SimulatedPnL).values(
        id=str(uuid.uuid4()),
        tenant_id=key["tenant_id"], market=key["market"], symbol=key["symbol"], timeframe=key["timeframe"],
        fee_bps=key["fee_bps"], slippage_bps=key["slippage_bps"],
        total_pnl=res["total_pnl"], max_drawdown=res["max_drawdown"], n_trades=res["n_trades"],
        equity_curve=res["equity_curve"]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["tenant_id","market","symbol","timeframe","fee_bps","slippage_bps"],
        set_={
            "total_pnl": stmt.excluded.total_pnl,
            "max_drawdown": stmt.excluded.max_drawdown,
            "n_trades": stmt.excluded.n_trades,
            "equity_curve": stmt.excluded.equity_curve,
        }
    ).returning(SimulatedPnL.id)
    row = await session.execute(stmt)
    rid = row.scalar_one()
    await session.commit()
    return rid
