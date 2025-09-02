import pandas as pd

def mean_reversion_signals(df: pd.DataFrame, rsi_buy: float = 30.0, rsi_sell: float = 70.0):
    out = df.copy()
    out["signal"] = 0
    out.loc[out["rsi"] <= rsi_buy, "signal"] = 1
    out.loc[out["rsi"] >= rsi_sell, "signal"] = -1
    # shift by 1 to avoid lookahead
    out["signal"] = out["signal"].shift(1).fillna(0).astype(int)
    return out

STRATEGY_REGISTRY = {
    "mean_reversion": mean_reversion_signals,
}
