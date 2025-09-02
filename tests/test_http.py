import httpx, os

BASE=os.getenv("BASE","http://127.0.0.1:8010")
H={"X-API-Key":"secret123"}

def test_health():
    r=httpx.get(f"{BASE}/health", headers=H, timeout=5)
    assert r.status_code==200 and r.json()["status"]=="ok"

def test_ready():
    r=httpx.get(f"{BASE}/ready", headers=H, timeout=5)
    assert r.status_code==200 and r.json()["ready"]==True

def test_metrics():
    r=httpx.get(f"{BASE}/metrics", headers=H, timeout=5)
    assert r.status_code==200 and "process_max_fds" in r.text
