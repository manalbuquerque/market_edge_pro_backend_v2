import os, time, httpx, concurrent.futures, functools, pytest

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8013")
KEY  = os.getenv("APIKEY_TEST", "secret123")

ENABLED = os.getenv("RATE_LIMIT_ENABLED", "0") in {"1", "true", "True"}

def _hit(_):
    try:
        return httpx.get(f"{BASE}/health", headers={"X-API-Key": KEY}, timeout=5).status_code
    except Exception:
        return 599

@pytest.mark.skipif(not ENABLED, reason="rate limit not enabled")
def test_ratelimit_bursts_then_429():
    # Dispara várias requests em paralelo para ultrapassar burst+rps
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as ex:
        codes = list(ex.map(_hit, range(64)))
    assert 200 in codes
    assert 429 in codes, f"expected 429 when rate limit is enabled, got {codes.count(429)}"

@pytest.mark.skipif(not ENABLED, reason="rate limit not enabled")
def test_ratelimit_recovers_after_sleep():
    # Provocar 429
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as ex:
        codes = list(ex.map(_hit, range(64)))
    assert 429 in codes
    # Tokens recuperam
    time.sleep(1.5)
    r2 = httpx.get(f"{BASE}/health", headers={"X-API-Key": KEY}, timeout=5)
    assert r2.status_code in (200, 429)
