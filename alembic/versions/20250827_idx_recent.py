from alembic import op

# revision identifiers, used by Alembic.
revision = "20250827_idx_recent"
down_revision = "20250825_02"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ohlcv_lookup
        ON ohlcv(tenant_id, market, symbol, timeframe, ts DESC);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_signals_lookup
        ON signals(tenant_id, market, symbol, timeframe, ts DESC);
    """)

def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_signals_lookup;")
    op.execute("DROP INDEX IF EXISTS idx_ohlcv_lookup;")

