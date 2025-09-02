# tests/test_smoke_endpoints.py
import os
import httpx

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8013")
GOOD = os.getenv("APIKEY_TEST", "secret123")

# ---------- /ohlcv/recent ----------
def test_ohlcv_recent_401_without_key():
    r = httpx.get(
        f"{BASE}/ohlcv/recent",
        params={"tenant_id": "t1", "market": "CRYPTO", "symbol": "BTCUSDT", "timeframe": "1m", "limit": 2},
        timeout=10,
    )
    assert r.status_code == 401

def test_ohlcv_recent_200_with_key():
    r = httpx.get(
        f"{BASE}/ohlcv/recent",
        params={"tenant_id": "t1", "market": "CRYPTO", "symbol": "BTCUSDT", "timeframe": "1m", "limit": 2},
        headers={"X-API-Key": GOOD},
        timeout=10,
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    if data:
        row = data[0]
        for k in ("tenant_id", "market", "symbol", "timeframe", "ts", "open", "high", "low", "close", "volume"):
            assert k in row

# ---------- /signals/recent ----------
def test_signals_recent_401_without_key():
    r = httpx.get(
        f"{BASE}/signals/recent",
        params={"tenant_id": "t1", "market": "CRYPTO", "symbol": "BTCUSDT", "timeframe": "1m", "limit": 2},
        timeout=10,
    )
    assert r.status_code == 401

def test_signals_recent_200_with_key():
    r = httpx.get(
        f"{BASE}/signals/recent",
        params={"tenant_id": "t1", "market": "CRYPTO", "symbol": "BTCUSDT", "timeframe": "1m", "limit": 2},
        headers={"X-API-Key": GOOD},
        timeout=10,
    )
    assert r.status_code == 200
    data = r.json()
    for k in ("tenant_id", "market", "symbol", "timeframe", "count", "signals"):
        assert k in data
    assert isinstance(data["signals"], list)

# ---------- /signals/window ----------
def test_signals_window_200_with_key():
    r = httpx.get(
        f"{BASE}/signals/window",
        params={
            "tenant_id": "t1",
            "market": "CRYPTO",
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "since": 1_600_000_000,
            "until": 2_000_000_000,
            "limit": 10,
        },
        headers={"X-API-Key": GOOD},
        timeout=10,
    )
    assert r.status_code == 200
    data = r.json()
    for k in ("tenant_id", "market", "symbol", "timeframe", "count", "signals"):
        assert k in data
    assert isinstance(data["signals"], list)

# ---------- validação de input ----------
def test_ohlcv_recent_422_bad_limit_with_key():
    r = httpx.get(
        f"{BASE}/ohlcv/recent",
        params={"tenant_id": "t1", "market": "CRYPTO", "symbol": "BTCUSDT", "timeframe": "1m", "limit": 0},
        headers={"X-API-Key": GOOD},
        timeout=10,
    )
    assert r.status_code in (400, 422)
