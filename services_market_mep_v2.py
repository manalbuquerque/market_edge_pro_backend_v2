from typing import Optional, List, Dict
import logging, traceback
from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from db_mep_v2 import get_session_optional
from services_storage_mep_v2 import read_ohlcv, upsert_ohlcv
from services_binance_public_mep_v1 import get_klines, get_klines_range

logger = logging.getLogger("mep.data")
router = APIRouter(tags=["data-v2"])

BINANCE_TF_ALLOWED = {"1s","1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d","3d","1w","1M"}

async def fetch_binance_ohlcv(symbol: str, timeframe: str, since: Optional[int], until: Optional[int], limit: Optional[int] = None) -> List[Dict]:
    if timeframe not in BINANCE_TF_ALLOWED:
        raise ValueError(f"invalid timeframe '{timeframe}'")
    if since is not None and until is not None:
        if until <= since:
            raise ValueError("until must be > since (epoch ms)")
        return await get_klines_range(symbol, timeframe, since, until)
    return await get_klines(symbol, timeframe, limit=int(limit) if limit else 1000)

async def get_or_fetch_and_persist(session: Optional[AsyncSession], tenant_id: str, market: str, symbol: str, timeframe: str,
                                   since: Optional[int], until: Optional[int], persist: bool, limit: Optional[int] = None) -> Dict:
    # Lê DB só se persist=True e existir sessão
    if persist and session is not None:
        try:
            rows = await read_ohlcv(session, tenant_id, market, symbol, timeframe, since, until)
        except SQLAlchemyError:
            rows = []
        if rows:
            return {"source": "db", "rows": rows}

    fetched = await fetch_binance_ohlcv(symbol, timeframe, since, until, limit=limit)

    if persist and session is not None and fetched:
        try:
            await upsert_ohlcv(session, tenant_id, market, symbol, timeframe, fetched)
        except SQLAlchemyError:
            pass

    return {"source": "binance", "rows": fetched}

@router.get("/data/ohlcv")
async def ohlcv(
    market: str = Query("binance", description="Apenas 'binance' suportado"),
    symbol: str = Query(..., min_length=6, description="Ex.: BTCUSDT"),
    tf: str = Query("1h", alias="tf", description="1m,5m,1h,4h,1d,..."),
    since: Optional[int] = Query(None, description="epoch ms início"),
    until: Optional[int] = Query(None, description="epoch ms fim"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="apenas sem since/until"),
    persist: bool = Query(False, description="upsert em Timescale"),
    tenant_id: str = Query("default"),
    session: Optional[AsyncSession] = Depends(get_session_optional),
):
    if market.lower() != "binance":
        raise HTTPException(status_code=400, detail="Only 'binance' supported.")
    symbol_u = symbol.upper()
    try:
        payload = await get_or_fetch_and_persist(session, tenant_id, market, symbol_u, tf, since, until, persist, limit)
        return {"market": market, "symbol": symbol_u, "timeframe": tf, "source": payload["source"], "rows": payload["rows"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("ohlcv failed: %s", e)
        logger.debug("trace:\n%s", "".join(traceback.format_exc()))
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {e}")

# Endpoint de debug: Binance direto
@router.get("/data/ohlcv_direct")
async def ohlcv_direct(symbol: str = Query(..., min_length=6), tf: str = Query("1h"), limit: Optional[int] = Query(5, ge=1, le=1000)):
    rows = await get_klines(symbol.upper(), tf, limit=int(limit))
    return {"market": "binance", "symbol": symbol.upper(), "timeframe": tf, "source": "binance", "rows": rows}





