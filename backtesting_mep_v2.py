from typing import Dict, Tuple, List
import numpy as np, pandas as pd

def fees_slippage(close_now: float, close_prev: float, pos: int, fee_bps: float, slippage_bps: float) -> float:
    ret = 0.0
    if pos != 0:
        ret += pos * (close_now - close_prev) / close_prev
    cost = (fee_bps + slippage_bps)/1e4 if pos != 0 else 0.0
    return ret - cost

def event_backtest(df: pd.DataFrame, signal_col: str="signal", fee_bps: float=10.0, slippage_bps: float=5.0):
    c = df["close"].to_numpy(); sig = df[signal_col].to_numpy()
    pos = 0; pnl = 0.0; eq = [1.0]; trades=[]
    for i in range(1, len(df)):
        desired = sig[i]
        if desired != pos:
            # close previous exposure cost + open new
            pnl += fees_slippage(c[i], c[i-1], pos, fee_bps, slippage_bps)
            pos = desired
            side = "BUY" if pos==1 else ("SELL" if pos==-1 else "FLAT")
            if side != "FLAT": trades.append((int(df["ts"].iloc[i]), side, float(c[i]), 1.0))
            pnl -= (fee_bps + slippage_bps)/1e4
        else:
            pnl += fees_slippage(c[i], c[i-1], pos, 0.0, 0.0)
        eq.append(1.0 + pnl)
    dd = float(np.max(np.maximum.accumulate(eq) - eq))
    return float(pnl), dd, trades, np.asarray(eq, float)

def purged_kfold(n: int, k: int=5, purge: int=20):
    fold = n // k
    for i in range(k):
        te_start = i*fold; te_end = (i+1)*fold if i<k-1 else n
        tr_end = max(te_start - purge, 0)
        yield slice(0,tr_end), slice(te_start, te_end)

def walk_forward_anchored(n: int, window: int=500, step: int=100):
    start=0
    while start+window<=n:
        yield slice(0, start), slice(start, start+window)
        start += step
