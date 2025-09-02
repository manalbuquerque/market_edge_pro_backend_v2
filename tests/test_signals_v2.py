# tests/test_signals_v2.py
import os, time, random, httpx

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8010")

def test_bulk_recent_window_roundtrip():
    tenant, market, symbol, tf = "t1", "CRYPTO", "BTCUSDT", "1m"
    now_ms = int(time.time() * 1000)
    base = now_ms - 5*60*1000
    pts = [{"ts": base + i*60*1000, "signal": random.choice([-1,0,1])} for i in range(5)]

    r = httpx.post(f"{BASE}/signals/bulk", json={
        "tenant_id": tenant, "market": market, "symbol": symbol, "timeframe": tf,
        "mode": "append", "signals": pts
    }, timeout=15)
    assert r.status_code == 200

    r2 = httpx.get(f"{BASE}/signals/recent", params={
        "tenant_id": tenant, "market": market, "symbol": symbol, "timeframe": tf, "limit": 10
    }, timeout=15)
    assert r2.status_code == 200
    jr2 = r2.json()
    assert jr2["tenant_id"] == tenant
    assert jr2["market"] == "crypto"
    assert jr2["symbol"] == "BTCUSDT"
    assert jr2["timeframe"] == "1m"
    assert isinstance(jr2["signals"], list)

    since, until = pts[1]["ts"], pts[-1]["ts"] + 1
    r3 = httpx.get(f"{BASE}/signals/window", params={
        "tenant_id": tenant, "market": market, "symbol": symbol, "timeframe": tf,
        "since": since, "until": until, "limit": 50
    }, timeout=15)
    assert r3.status_code == 200
    jr3 = r3.json()
    assert all(since <= int(x["ts"]) < until for x in jr3["signals"])
