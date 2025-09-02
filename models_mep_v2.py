from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Text, BigInteger, Float, JSON, TIMESTAMP, text, UniqueConstraint

Base = declarative_base()

class OHLCV(Base):
    __tablename__ = "ohlcv"
    tenant_id = Column(String, primary_key=True, default="default")
    market = Column(String, primary_key=True)
    symbol = Column(String, primary_key=True)
    timeframe = Column(String, primary_key=True)
    ts = Column(BigInteger, primary_key=True)  # epoch ms
    open = Column(Float); high = Column(Float); low = Column(Float); close = Column(Float); volume = Column(Float)

class Run(Base):
    __tablename__ = "runs"
    id = Column(String, primary_key=True)  # uuid
    tenant_id = Column(String, nullable=False, default="default")
    kind = Column(String, nullable=False)  # backtest|optimize|indicators
    status = Column(String, nullable=False, default="queued")
    params = Column(JSON, nullable=False)
    result = Column(JSON)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

class Signal(Base):
    __tablename__ = "signals"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    market = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    ts = Column(BigInteger, nullable=False)
    payload = Column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint('tenant_id','market','symbol','timeframe','ts', name='uq_signal_key'),)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(String, primary_key=True)
    who = Column(String, nullable=False)
    what = Column(Text, nullable=False)
    prev_hash = Column(String)
    this_hash = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))


# === NEW: Metrics models (v2) ===
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Integer

class AccuracyMetric(Base):
    __tablename__ = "accuracy_metrics"
    id = Column(String, primary_key=True)  # uuid
    tenant_id = Column(String, nullable=False, default="default")
    market = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    horizon_bars = Column(Integer, nullable=False, default=24)
    sample_count = Column(Integer, nullable=False, default=0)
    hit_count = Column(Integer, nullable=False, default=0)
    accuracy = Column(Float, nullable=False, default=0.0)
    details = Column(JSONB)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    __table_args__ = (UniqueConstraint('tenant_id','market','symbol','timeframe','horizon_bars', name='uq_accuracy_key'),)

class SimulatedPnL(Base):
    __tablename__ = "simulated_pnl"
    id = Column(String, primary_key=True)  # uuid
    tenant_id = Column(String, nullable=False, default="default")
    market = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    fee_bps = Column(Float, nullable=False, default=10.0)
    slippage_bps = Column(Float, nullable=False, default=5.0)
    total_pnl = Column(Float, nullable=False, default=0.0)
    max_drawdown = Column(Float, nullable=False, default=0.0)
    n_trades = Column(Integer, nullable=False, default=0)
    equity_curve = Column(JSONB)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    __table_args__ = (UniqueConstraint('tenant_id','market','symbol','timeframe','fee_bps','slippage_bps', name='uq_pnl_key'),)
