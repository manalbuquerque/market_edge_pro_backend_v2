# tests/test_signals_bulk_integration.py
import os
import time
import httpx

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8013")
KEY = os.getenv("APIKEY_TEST", "secret123")

TENANT = "t1"
MARKET = "CRYPTO"
SYMBOL = "BTCUSDT"
TF = "1m"


def _bulk_body(ts1: int, ts2: int):
    return {
        "tenant_id": TENANT,
        "market": MARKET,
        "symbol": SYMBOL,
        "timeframe": TF,
        "mode": "append",
        "signals": [
            {"ts": ts1, "signal": 1},
            {"ts": ts2, "signal": 0},
        ],
    }


def test_bulk_401_without_key():
    ts0 = int(time.time())
    r = httpx.post(f"{BASE}/signals/bulk", json=_bulk_body(ts0 + 10, ts0 + 20), timeout=10)
    assert r.status_code == 401


def test_bulk_append_roundtrip_ok():
    ts0 = int(time.time())
    ts1, ts2 = ts0 + 120, ts0 + 180

    # POST append
    r_post = httpx.post(
        f"{BASE}/signals/bulk",
        headers={"X-API-Key": KEY},
        json=_bulk_body(ts1, ts2),
        timeout=10,
    )
    assert r_post.status_code == 200
    j = r_post.json()
    # esquema de resposta estável
    for k in ("tenant_id", "market", "symbol", "timeframe", "mode", "inserted", "replaced"):
        assert k in j
    assert j["mode"] == "append"
    assert j["inserted"] >= 0  # pode ser 0 se já existirem

    # GET janela que cobre os TS inseridos
    r_get = httpx.get(
        f"{BASE}/signals/window",
        headers={"X-API-Key": KEY},
        params={
            "tenant_id": TENANT,
            "market": MARKET,
            "symbol": SYMBOL,
            "timeframe": TF,
            "since": ts0,
            "until": ts0 + 600,
            "limit": 100,
        },
        timeout=10,
    )
    assert r_get.status_code == 200
    g = r_get.json()
    assert "signals" in g and isinstance(g["signals"], list)

    got_ts = {int(s["ts"]) for s in g["signals"]}
    # Pelo menos um dos TS deve estar presente após o append
    assert {ts1, ts2} & got_ts


def test_bulk_append_idempotent_same_payload_inserts_zero():
    ts0 = int(time.time())
    ts1, ts2 = ts0 + 300, ts0 + 360
    payload = _bulk_body(ts1, ts2)

    # 1ª chamada
    r1 = httpx.post(
        f"{BASE}/signals/bulk",
        headers={"X-API-Key": KEY},
        json=payload,
        timeout=10,
    )
    assert r1.status_code == 200
    ins1 = r1.json().get("inserted", 0)
    assert ins1 >= 0

    # 2ª chamada com exatamente o mesmo payload deve deduplicar
    r2 = httpx.post(
        f"{BASE}/signals/bulk",
        headers={"X-API-Key": KEY},
        json=payload,
        timeout=10,
    )
    assert r2.status_code == 200
    ins2 = r2.json().get("inserted", None)
    assert ins2 == 0
