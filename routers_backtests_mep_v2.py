import uuid, pandas as pd
from fastapi import APIRouter, Body
from typing import Dict, Any
from services_market_mep_v2 import fetch_binance_ohlcv
from indicators_mep_v2 import apply_default_indicators_v2 as apply_default_indicators
from strategies_mep_v1 import STRATEGY_REGISTRY
from backtesting_mep_v2 import event_backtest, purged_kfold, walk_forward_anchored

router = APIRouter(tags=["backtests-v2"])

@router.post("/backtests/ab")
async def backtest_ab(payload: Dict[str, Any] = Body(...)):
    symbol = payload.get("symbol","BTCUSDT"); tf = payload.get("timeframe","1h"); lookback=int(payload.get("lookback",1000))
    s1 = payload.get("strategy_a","mean_reversion"); p1 = payload.get("params_a",{})
    s2 = payload.get("strategy_b","mean_reversion"); p2 = payload.get("params_b",{"rsi_sell":60.0,"rsi_buy":40.0})
    rows = await fetch_binance_ohlcv(symbol, tf, None, None)
    df = pd.DataFrame(rows).tail(lookback)
    df = apply_default_indicators(df)
    a = STRATEGY_REGISTRY[s1](df.copy(), **p1); b = STRATEGY_REGISTRY[s2](df.copy(), **p2)
    pnl_a, dd_a, tr_a, eq_a = event_backtest(a)
    pnl_b, dd_b, tr_b, eq_b = event_backtest(b)
    return {
      "symbol": symbol, "tf": tf,
      "A": {"pnl": pnl_a, "max_dd": dd_a, "trades": len(tr_a)},
      "B": {"pnl": pnl_b, "max_dd": dd_b, "trades": len(tr_b)}
    }

@router.post("/backtests/walkforward")
async def backtest_walkforward(payload: Dict[str, Any] = Body(...)):
    symbol = payload.get("symbol","BTCUSDT"); tf = payload.get("timeframe","1h"); lookback=int(payload.get("lookback",2000))
    window=int(payload.get("window",500)); step=int(payload.get("step",100))
    strat = payload.get("strategy","mean_reversion"); params = payload.get("params",{})
    rows = await fetch_binance_ohlcv(symbol, tf, None, None)
    df = pd.DataFrame(rows).tail(lookback)
    df = apply_default_indicators(df)
    segments=[]; total_pnl=0.0; worst_dd=0.0
    for tr_slice, te_slice in walk_forward_anchored(len(df), window=window, step=step):
        if te_slice.start==0:  # no in-sample before first window
            continue
        train = df.iloc[tr_slice]; test = df.iloc[te_slice]
        sig = STRATEGY_REGISTRY[strat](test.copy(), **params)  # params fixos; otimização OOS fica para v3
        pnl, dd, tr, eq = event_backtest(sig)
        total_pnl += pnl; worst_dd = max(worst_dd, dd)
        segments.append({"is": [int(df["ts"].iloc[tr_slice.start] if tr_slice.start>0 else df["ts"].iloc[0]), int(df["ts"].iloc[tr_slice.stop-1])],
                         "oos": [int(df["ts"].iloc[te_slice.start]), int(df["ts"].iloc[te_slice.stop-1])],
                         "pnl": pnl, "dd": dd})
    return {"symbol": symbol, "tf": tf, "segments": segments, "total_pnl": total_pnl, "worst_dd": worst_dd}
