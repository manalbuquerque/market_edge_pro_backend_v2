import asyncio, random, sys
from typing import List, Dict, Optional
import httpx
from config_mep_v2 import settings

BINANCE_MAX_LIMIT = 1000

async def _retry_get(client: httpx.AsyncClient, url: str, params: dict, tries: int = 4, backoff: float = 0.5):
    for i in range(tries):
        try:
            r = await client.get(url, params=params, timeout=settings.REQUEST_TIMEOUT)
            if r.status_code in (418, 429):
                wait = float(r.headers.get("Retry-After", (i + 1) * backoff))
                await asyncio.sleep(wait); continue
            r.raise_for_status()
            return r.json()
        except Exception:
            if i == tries - 1:
                raise
            await asyncio.sleep((i + 1) * backoff + random.uniform(0, 0.25))

def _normalize_klines(rows: List[List]) -> List[Dict]:
    return [{"ts": int(k[0]), "open": float(k[1]), "high": float(k[2]), "low": float(k[3]),
             "close": float(k[4]), "volume": float(k[5])} for k in rows]

async def get_klines(symbol: str, interval: str,
                     start_ms: Optional[int] = None, end_ms: Optional[int] = None,
                     limit: int = BINANCE_MAX_LIMIT) -> List[Dict]:
    url = f"{settings.BINANCE_BASE}/api/v3/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": min(limit, BINANCE_MAX_LIMIT)}
    if start_ms is not None: params["startTime"] = int(start_ms)
    if end_ms is not None: params["endTime"] = int(end_ms)
    async with httpx.AsyncClient(http2=False) as client:
        data = await _retry_get(client, url, params)
    return _normalize_klines(data)

async def get_klines_range(symbol: str, interval: str, start_ms: int, end_ms: int,
                           step_limit: int = BINANCE_MAX_LIMIT) -> List[Dict]:
    url = f"{settings.BINANCE_BASE}/api/v3/klines"
    out: List[Dict] = []
    params = {"symbol": symbol.upper(), "interval": interval, "limit": min(step_limit, BINANCE_MAX_LIMIT)}
    cur = start_ms
    async with httpx.AsyncClient(http2=False) as client:
        while True:
            p = dict(params); p["startTime"] = int(cur); p["endTime"] = int(end_ms)
            rows = await _retry_get(client, url, p)
            if not rows: break
            norm = _normalize_klines(rows); out.extend(norm)
            last_ts = norm[-1]["ts"]
            if last_ts >= end_ms or len(rows) < step_limit: break
            cur = last_ts + 1
            await asyncio.sleep(0.05)
    return out

if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    async def _main():
        rows = await get_klines(sym, "1h", limit=5)
        print(sym, "rows=", len(rows), "first=", rows[:1])
    asyncio.run(_main())
