from __future__ import annotations

from typing import List, Dict, Any, Literal
from sqlalchemy import text

def read_signals(
    session,
    *,
    tenant_id: str,
    market: str,
    symbol: str,
    timeframe: str,
    since: int | None,
    until: int | None,
    limit: int,
) -> List[Dict[str, Any]]:
    params = {
        "tenant_id": tenant_id,
        "market": market.upper(),
        "symbol": symbol.upper(),
        "timeframe": timeframe.lower(),
        "limit": limit,
    }
    filters = [
        "tenant_id = :tenant_id",
        "market = :market",
        "symbol = :symbol",
        "timeframe = :timeframe",
    ]
    if since is not None:
        filters.append("ts >= :since")
        params["since"] = since
    if until is not None:
        filters.append("ts < :until")
        params["until"] = until

    q = text(f"""
        SELECT id, tenant_id, market, symbol, timeframe, payload, ts, created_at
        FROM signals
        WHERE {" AND ".join(filters)}
        ORDER BY ts DESC
        LIMIT :limit
    """)
    rows = session.execute(q, params).mappings().all()
    return [dict(r) for r in rows]

def upsert_signals(
    session,
    *,
    tenant_id: str,
    market: str,
    symbol: str,
    timeframe: str,
    mode: Literal["replace", "append"],
    signals: List[Dict[str, int]],
) -> Dict[str, Any]:
    # normalize
    market_u = market.upper()
    symbol_u = symbol.upper()
    timeframe_l = timeframe.lower()

    if mode == "replace":
        session.execute(
            text("""
                DELETE FROM signals
                WHERE tenant_id=:tenant_id AND market=:market
                  AND symbol=:symbol AND timeframe=:timeframe
            """),
            {
                "tenant_id": tenant_id,
                "market": market_u,
                "symbol": symbol_u,
                "timeframe": timeframe_l,
            },
        )

    if not signals:
        session.commit()
        return {"inserted": 0, "replaced": mode == "replace"}

    # Insert with ON CONFLICT to avoid duplicates on same composite key
    # Your unique key is (tenant_id, market, symbol, timeframe, ts)
    inserted = 0
    insert_sql = text("""
        INSERT INTO signals (id, tenant_id, market, symbol, timeframe, payload, ts)
        VALUES (gen_random_uuid(), :tenant_id, :market, :symbol, :timeframe, :payload, :ts)
        ON CONFLICT (tenant_id, market, symbol, timeframe, ts)
        DO UPDATE SET payload = EXCLUDED.payload
    """)

    for s in signals:
        session.execute(
            insert_sql,
            {
                "tenant_id": tenant_id,
                "market": market_u,
                "symbol": symbol_u,
                "timeframe": timeframe_l,
                # store a light JSON with the numeric `signal`
                "payload": {"signal": int(s["signal"])},
                "ts": int(s["ts"]),
            },
        )
        inserted += 1

    session.commit()
    return {"inserted": inserted, "replaced": mode == "replace"}