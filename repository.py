# repository.py
from __future__ import annotations
from typing import Iterable, Sequence

from sqlalchemy import text
from db_mep_v2 import engine  # FIX: antes era from app.db import engine

def _chunks(it: Iterable, n: int):
    it = iter(it)
    while True:
        buf = []
        for _ in range(n):
            try:
                buf.append(next(it))
            except StopIteration:
                if buf:
                    yield buf
                return
        yield buf

def upsert_ohlcv(rows: Sequence, chunk_size: int = 2000) -> int:
    """
    rows: sequência de objetos Pydantic ou dicts com:
      tenant_id, market, symbol, timeframe, ts, open, high, low, close, volume
    """
    sql = text("""
        INSERT INTO ohlcv(tenant_id,market,symbol,timeframe,ts,open,high,low,close,volume)
        VALUES (:tenant_id,:market,:symbol,:timeframe,:ts,:open,:high,:low,:close,:volume)
        ON CONFLICT (tenant_id,market,symbol,timeframe,ts) DO UPDATE SET
          open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
          close=EXCLUDED.close, volume=EXCLUDED.volume
    """)
    def to_dict(r):
        return r.model_dump() if hasattr(r, "model_dump") else dict(r)
    total = 0
    with engine.begin() as conn:
        for chunk in _chunks(rows, chunk_size):
            conn.execute(sql, [to_dict(r) for r in chunk])
            total += len(chunk)
    return total

def upsert_signals(rows: Sequence, chunk_size: int = 2000) -> int:
    """
    rows: sequência com:
      tenant_id, market, symbol, strategy, timeframe, ts, side, strength
    """
    sql = text("""
        INSERT INTO signals(tenant_id,market,symbol,strategy,timeframe,ts,side,strength)
        VALUES (:tenant_id,:market,:symbol,:strategy,:timeframe,:ts,:side,:strength)
        ON CONFLICT (tenant_id,market,symbol,strategy,timeframe,ts) DO UPDATE SET
          side=EXCLUDED.side, strength=EXCLUDED.strength
    """)
    def to_dict(r):
        return r.model_dump() if hasattr(r, "model_dump") else dict(r)
    total = 0
    with engine.begin() as conn:
        for chunk in _chunks(rows, chunk_size):
            conn.execute(sql, [to_dict(r) for r in chunk])
            total += len(chunk)
    return total
