
import numpy as np
import pandas as pd
from services_metrics_mep_v2 import compute_accuracy, compute_pnl

def _toy_df(n=200, seed=0):
    rng = np.random.default_rng(seed)
    ts = np.arange(n, dtype=np.int64) * 60000
    price = 100 + rng.normal(0, 0.5, size=n).cumsum()
    high = price + rng.random(size=n)
    low = price - rng.random(size=n)
    vol = rng.integers(100, 1000, size=n).astype(float)
    return pd.DataFrame({"ts": ts, "open": price, "high": high, "low": low, "close": price, "volume": vol})

def _toy_signal(df):
    ema = df["close"].ewm(span=20, adjust=False).mean()
    s = (df["close"] > ema).astype(int) - (df["close"] < ema).astype(int)
    return pd.Series(s.to_numpy(), index=df["ts"], name="signal")

def test_compute_accuracy_basic():
    df = _toy_df(300)
    sig = _toy_signal(df)
    res = compute_accuracy(df, sig, horizon_bars=10)
    assert isinstance(res, dict)
    assert res["samples"] > 0
    assert 0.0 <= res["accuracy"] <= 1.0

def test_compute_pnl_runs():
    df = _toy_df(400, seed=42)
    sig = _toy_signal(df)
    res = compute_pnl(df, sig, fee_bps=10.0, slippage_bps=5.0)
    assert "total_pnl" in res and "max_drawdown" in res and "n_trades" in res and "equity_curve" in res
    assert isinstance(res["equity_curve"], list) and len(res["equity_curve"]) == len(df)
