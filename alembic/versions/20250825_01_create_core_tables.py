"""create core tables (TimescaleDB)
Revision ID: 20250825_01
Revises:
Create Date: 2025-08-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20250825_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Extensions needed (safe if already exist)
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")  # for gen_random_uuid()

    # --- OHLCV (hypertable on ts)
    op.create_table(
        "ohlcv",
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("market", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("ts", sa.BigInteger, nullable=False),  # ms since epoch
        sa.Column("open", sa.Numeric(20, 10), nullable=False),
        sa.Column("high", sa.Numeric(20, 10), nullable=False),
        sa.Column("low", sa.Numeric(20, 10), nullable=False),
        sa.Column("close", sa.Numeric(20, 10), nullable=False),
        sa.Column("volume", sa.Numeric(28, 10), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "market", "symbol", "timeframe", "ts"),
    )
    op.create_index(
        "ix_ohlcv_lookup", "ohlcv", ["tenant_id", "market", "symbol", "timeframe", "ts"]
    )
    op.execute("SELECT create_hypertable('ohlcv','ts', if_not_exists => TRUE);")

    # --- Signals (payload JSONB, hypertable on ts)
    op.create_table(
        "signals",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("market", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("ts", sa.BigInteger, nullable=False),  # ms since epoch
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", "market", "symbol", "timeframe", "ts", name="uq_signals_key"),
    )
    op.create_index(
        "idx_signals_lookup",
        "signals",
        ["tenant_id", "market", "symbol", "timeframe", "ts"],
    )
    op.execute("SELECT create_hypertable('signals','ts', if_not_exists => TRUE);")

    # --- Accuracy metrics (optional analytics)
    op.create_table(
        "accuracy_metrics",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("market", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("lookback", sa.Integer, nullable=False),
        sa.Column("horizon_bars", sa.Integer, nullable=False),
        sa.Column("accuracy", sa.Numeric(12, 8), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_accuracy_key",
        "accuracy_metrics",
        ["tenant_id", "market", "symbol", "timeframe", "created_at"],
    )

    # --- Simulated PnL (optional analytics)
    op.create_table(
        "simulated_pnl",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("market", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("lookback", sa.Integer, nullable=False),
        sa.Column("fee_bps", sa.Numeric(10, 4), nullable=False),
        sa.Column("slippage_bps", sa.Numeric(10, 4), nullable=False),
        sa.Column("total_return", sa.Numeric(18, 8), nullable=False),
        sa.Column("n_trades", sa.Integer, nullable=False),
        sa.Column("sharpe", sa.Numeric(18, 8), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_pnl_key",
        "simulated_pnl",
        ["tenant_id", "market", "symbol", "timeframe", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_pnl_key", table_name="simulated_pnl")
    op.drop_table("simulated_pnl")
    op.drop_index("ix_accuracy_key", table_name="accuracy_metrics")
    op.drop_table("accuracy_metrics")
    op.drop_index("idx_signals_lookup", table_name="signals")
    op.drop_constraint("uq_signals_key", "signals", type_="unique")
    op.drop_table("signals")
    op.drop_index("ix_ohlcv_lookup", table_name="ohlcv")
    op.drop_table("ohlcv")