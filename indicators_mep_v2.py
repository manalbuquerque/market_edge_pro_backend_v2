import numpy as np
import pandas as pd
import math

# -------------------------------
# Helpers
# -------------------------------

def _ema(arr: np.ndarray, span: int) -> np.ndarray:
    return pd.Series(arr).ewm(span=span, adjust=False).mean().to_numpy()

# -------------------------------
# Moving Averages
# -------------------------------

def sma(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    out = df.copy()
    out[f"sma{period}"] = df["close"].rolling(period).mean()
    return out

def ema(df: pd.DataFrame, span: int = 20) -> pd.DataFrame:
    out = df.copy()
    out[f"ema{span}"] = _ema(out["close"].to_numpy(), span)
    return out

def wma(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    weights = np.arange(1, period+1)
    out = df.copy()
    out[f"wma{period}"] = (
        df["close"].rolling(period).apply(lambda x: np.dot(x, weights)/weights.sum(), raw=True)
    )
    return out

def dema(df: pd.DataFrame, span: int = 20) -> pd.DataFrame:
    ema1 = pd.Series(df["close"]).ewm(span=span, adjust=False).mean()
    ema2 = ema1.ewm(span=span, adjust=False).mean()
    out = df.copy()
    out[f"dema{span}"] = 2*ema1 - ema2
    return out

def tema(df: pd.DataFrame, span: int = 20) -> pd.DataFrame:
    ema1 = pd.Series(df["close"]).ewm(span=span, adjust=False).mean()
    ema2 = ema1.ewm(span=span, adjust=False).mean()
    ema3 = ema2.ewm(span=span, adjust=False).mean()
    out = df.copy()
    out[f"tema{span}"] = 3*(ema1 - ema2) + ema3
    return out

def trima(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    out = df.copy()
    out[f"trima{period}"] = df["close"].rolling(period).mean().rolling(period).mean()
    return out

# -------------------------------
# Oscillators
# -------------------------------

def rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    close = df["close"].to_numpy()
    delta = np.diff(close, prepend=close[0])
    up = np.where(delta > 0, delta, 0.0)
    down = np.where(delta < 0, -delta, 0.0)
    roll_up = pd.Series(up).ewm(alpha=1/period, adjust=False).mean().to_numpy()
    roll_down = pd.Series(down).ewm(alpha=1/period, adjust=False).mean().to_numpy()
    rs = np.divide(roll_up, np.where(roll_down==0, np.nan, roll_down))
    rsi = 100 - (100 / (1 + rs))
    out = df.copy()
    out["rsi"] = np.nan_to_num(rsi, nan=50.0)
    return out

def stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
    low_min = df["low"].rolling(window=k_period).min()
    high_max = df["high"].rolling(window=k_period).max()
    k = 100 * (df["close"] - low_min) / (high_max - low_min)
    d = k.rolling(window=d_period).mean()
    out = df.copy()
    out["stoch_k"] = k
    out["stoch_d"] = d
    return out

def cci(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    ma = tp.rolling(period).mean()
    md = (tp - ma).abs().rolling(period).mean()
    cci = (tp - ma) / (0.015 * md)
    out = df.copy()
    out["cci"] = cci
    return out

def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high, low, close = df["high"], df["low"], df["close"]
    plus_dm = high.diff().clip(lower=0)
    minus_dm = -low.diff().clip(lower=0)
    tr = pd.concat([(high-low), (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period).mean() / atr)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.ewm(alpha=1/period).mean()
    out = df.copy()
    out["adx"] = adx
    return out

# -------------------------------
# Trend / Volatility
# -------------------------------

def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    fast_ = _ema(df["close"].to_numpy(), fast)
    slow_ = _ema(df["close"].to_numpy(), slow)
    macd_line = fast_ - slow_
    signal_line = pd.Series(macd_line).ewm(span=signal, adjust=False).mean().to_numpy()
    hist = macd_line - signal_line
    out = df.copy()
    out["macd"] = macd_line
    out["macd_signal"] = signal_line
    out["macd_hist"] = hist
    return out

def atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1).fillna(close.iloc[0])
    tr = pd.concat([high-low, (high-prev_close).abs(), (low-prev_close).abs()], axis=1).max(axis=1)
    out = df.copy()
    out["atr"] = tr.ewm(alpha=1/period, adjust=False).mean()
    return out

def bollinger(df: pd.DataFrame, period: int = 20, k: float = 2.0) -> pd.DataFrame:
    s = df["close"]
    ma = s.rolling(period).mean()
    std = s.rolling(period).std(ddof=0)
    out = df.copy()
    out["bb_mid"] = ma
    out["bb_up"] = ma + k*std
    out["bb_low"] = ma - k*std
    return out

# -------------------------------
# Volume Indicators
# -------------------------------

def obv(df: pd.DataFrame) -> pd.DataFrame:
    obv = (np.sign(df["close"].diff()) * df["volume"]).fillna(0).cumsum()
    out = df.copy()
    out["obv"] = obv
    return out

def vwap(df: pd.DataFrame) -> pd.DataFrame:
    cum_vol = df["volume"].cumsum()
    cum_vol_price = (df["close"] * df["volume"]).cumsum()
    out = df.copy()
    out["vwap"] = cum_vol_price / cum_vol
    return out

def mfi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    mf = tp * df["volume"]
    pos_mf = mf.where(tp > tp.shift(1), 0.0)
    neg_mf = mf.where(tp < tp.shift(1), 0.0)
    mr = pos_mf.rolling(period).sum() / neg_mf.rolling(period).sum()
    mfi = 100 - (100 / (1 + mr))
    out = df.copy()
    out["mfi"] = mfi
    return out

# -------------------------------
# Ichimoku Cloud
# -------------------------------

def ichimoku(df: pd.DataFrame) -> pd.DataFrame:
    high9 = df["high"].rolling(9).max()
    low9 = df["low"].rolling(9).min()
    tenkan = (high9 + low9) / 2
    high26 = df["high"].rolling(26).max()
    low26 = df["low"].rolling(26).min()
    kijun = (high26 + low26) / 2
    span_a = ((tenkan + kijun) / 2).shift(26)
    high52 = df["high"].rolling(52).max()
    low52 = df["low"].rolling(52).min()
    span_b = ((high52 + low52) / 2).shift(26)
    chikou = df["close"].shift(-26)
    out = df.copy()
    out["ichimoku_tenkan"] = tenkan
    out["ichimoku_kijun"] = kijun
    out["ichimoku_span_a"] = span_a
    out["ichimoku_span_b"] = span_b
    out["ichimoku_chikou"] = chikou
    return out

# -------------------------------
# Apply default set
# -------------------------------

def apply_default_indicators_v2(df: pd.DataFrame) -> pd.DataFrame:
    out = ema(df, 20)
    out = sma(out, 20)
    out = rsi(out, 14)
    out = macd(out, 12, 26, 9)
    out = atr(out, 14)
    out = bollinger(out, 20, 2.0)
    out = obv(out)
    out = vwap(out)
    out = stochastic(out, 14, 3)
    return out
