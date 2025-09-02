from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional
from db_mep_v2 import get_session
from services_storage_mep_v2 import read_ohlcv, upsert_ohlcv
from services_market_mep_v2 import fetch_binance_ohlcv

router = APIRouter(tags=["data-v2"])

@router.get("/data/ohlcv")
async def ohlcv_v2(
    market: str = Query("binance"),
    symbol: str = Query(..., min_length=6),
    tf: str = Query("1h"),
    since: Optional[int] = Query(None, description="epoch ms"),
    until: Optional[int] = Query(None, description="epoch ms"),
    tenant_id: str = Query("default"),
    persist: bool = Query(True, description="se True, faz upsert no Timescale"),
    session = Depends(get_session)
):
    if market.lower() != "binance":
        raise HTTPException(status_code=400, detail="Only 'binance' supported.")
    rows = await read_ohlcv(session, tenant_id, market, symbol.upper(), tf, since, until)
    if rows:
        return {"source": "db", "market": market, "symbol": symbol.upper(), "timeframe": tf, "rows": rows}
    fetched = await fetch_binance_ohlcv(symbol, tf, since, until)
    if persist and fetched:
        await upsert_ohlcv(session, tenant_id, market, symbol.upper(), tf, fetched)
    return {"source": "binance", "market": market, "symbol": symbol.upper(), "timeframe": tf, "rows": fetched}
