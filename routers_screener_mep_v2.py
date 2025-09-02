from fastapi import APIRouter, Query, Depends
from typing import Optional, List, Dict, Any
from db_mep_v2 import get_session
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["screener-v2"])

def _build_clause(filters: Dict[str, Any]):
    where = ["1=1"]; params = {}
    if "symbol_contains" in filters and filters["symbol_contains"]:
        where.append("symbol ILIKE :sym")
        params["sym"] = f"%{filters['symbol_contains']}%"
    if "min_volume" in filters and filters["min_volume"] is not None:
        where.append("volume >= :minvol"); params["minvol"] = float(filters["min_volume"])
    return " AND ".join(where), params

@router.get("/screener")
async def screener(
    market: str = Query("binance"),
    timeframe: str = Query("1h"),
    sort_by: str = Query("ts"),
    sort_dir: str = Query("desc"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    symbol_contains: Optional[str] = None,
    min_volume: Optional[float] = None,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = "default"
):
    where, params = _build_clause({"symbol_contains": symbol_contains, "min_volume": min_volume})
    params.update(dict(tenant_id=tenant_id, market=market, timeframe=timeframe, limit=limit, offset=offset))
    sort = f"{sort_by} {('DESC' if sort_dir.lower()=='desc' else 'ASC')}"
    q = f"""
      WITH last AS (
        SELECT symbol, MAX(ts) AS ts
        FROM ohlcv
        WHERE tenant_id=:tenant_id AND market=:market AND timeframe=:timeframe
        GROUP BY symbol
      )
      SELECT o.symbol, o.ts, o.close, o.volume
      FROM ohlcv o
      JOIN last l ON l.symbol=o.symbol AND l.ts=o.ts
      WHERE {where}
      ORDER BY {sort}
      LIMIT :limit OFFSET :offset
    """
    res = await session.execute(q, params)
    rows = [dict(symbol=r[0], ts=int(r[1]), close=float(r[2]), volume=float(r[3])) for r in res.fetchall()]
    return {"items": rows, "offset": offset, "limit": limit}
