import pytest, httpx

@pytest.mark.asyncio
async def test_health():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8010",
                                 headers={"X-API-Key":"secret123"}) as c:
        r = await c.get("/health")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"
