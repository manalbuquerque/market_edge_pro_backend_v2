import httpx
import os

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8010")

def test_recent_basic():
    r = httpx.get(f"{BASE}/ohlcv/recent", params={
        "tenant_id": "t1",
        "market": "CRYPTO",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "limit": 2,
    }, timeout=10)

    # resposta deve ser 200
    assert r.status_code == 200

    data = r.json()
    # deve ser lista com no máximo 2 registos
    assert isinstance(data, list) and len(data) <= 2

    if data:
        # cada registo deve ter estes campos
        required = {"ts", "open", "high", "low", "close", "volume"}
        assert required.issubset(data[0].keys())
