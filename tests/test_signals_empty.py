import pytest, httpx

BASE = "http://127.0.0.1:8010"
H = {"X-API-Key":"secret123"}

@pytest.mark.asyncio
async def test_signals_empty_200():
    async with httpx.AsyncClient(base_url=BASE, headers=H) as c:
        r = await c.get("/signals", params={"market":"CRYPTO","symbol":"BTCUSDT","timeframe":"1m","limit":1})
        assert r.status_code == 200
        body = r.json()
        assert "signals" in body
        assert body["tenant_id"] == "default"
