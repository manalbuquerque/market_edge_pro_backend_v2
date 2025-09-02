import os
import httpx

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8013")
GOOD = os.getenv("APIKEY_TEST", "secret123")


def test_health_no_header_401():
    r = httpx.get(f"{BASE}/health", timeout=5)
    assert r.status_code == 401
    assert r.headers.get("www-authenticate", "").lower().startswith("apikey")


def test_health_wrong_key_401():
    r = httpx.get(f"{BASE}/health", headers={"X-API-Key": "bad"}, timeout=5)
    assert r.status_code == 401


def test_health_good_key_200():
    r = httpx.get(f"{BASE}/health", headers={"X-API-Key": GOOD}, timeout=5)
    assert r.status_code == 200
    assert r.json().get("status") == "ok"
