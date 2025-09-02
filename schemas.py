# schemas.py
from __future__ import annotations
from typing import Literal, List
from pydantic import BaseModel, Field

class OHLCVIn(BaseModel):
    tenant_id: str = Field(max_length=64)
    market: str = Field(max_length=64)
    symbol: str = Field(max_length=64)
    timeframe: str = Field(max_length=16)
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float

class SignalIn(BaseModel):
    tenant_id: str = Field(max_length=64)
    market: str = Field(max_length=64)
    symbol: str = Field(max_length=64)
    strategy: str = Field(max_length=64)
    timeframe: str = Field(max_length=16)
    ts: int
    side: Literal["BUY", "SELL", "HOLD"]
    strength: float

class BulkOHLCV(BaseModel):
    rows: List[OHLCVIn] = Field(min_items=1, max_items=10000)

class BulkSignal(BaseModel):
    rows: List[SignalIn] = Field(min_items=1, max_items=10000)
