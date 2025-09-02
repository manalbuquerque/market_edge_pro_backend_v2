import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    BINANCE_BASE: str = os.getenv("BINANCE_BASE", "https://api.binance.com")
    REQUEST_TIMEOUT: float = float(os.getenv("REQUEST_TIMEOUT", "30"))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()  # ex: postgresql+asyncpg://user:pass@localhost:5432/market_edge

settings = Settings()

