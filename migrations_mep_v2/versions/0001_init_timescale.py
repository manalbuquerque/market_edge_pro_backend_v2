from alembic import op
import sqlalchemy as sa

revision = '0001_init_timescale'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    op.execute("""
    CREATE TABLE IF NOT EXISTS ohlcv (
        tenant_id text NOT NULL,
        market text NOT NULL,
        symbol text NOT NULL,
        timeframe text NOT NULL,
        ts bigint NOT NULL,
        open double precision, high double precision, low double precision, close double precision, volume double precision,
        PRIMARY KEY (tenant_id, market, symbol, timeframe, ts)
    );
    """)
    op.execute("SELECT create_hypertable('ohlcv','ts', if_not_exists => TRUE);")
    op.execute("""
    CREATE TABLE IF NOT EXISTS runs (
        id text PRIMARY KEY,
        tenant_id text NOT NULL,
        kind text NOT NULL,
        status text NOT NULL,
        params jsonb NOT NULL,
        result jsonb,
        created_at timestamptz DEFAULT now()
    );
    """)
    op.execute("""
    CREATE TABLE IF NOT EXISTS signals (
        id text PRIMARY KEY,
        tenant_id text NOT NULL,
        market text NOT NULL,
        symbol text NOT NULL,
        timeframe text NOT NULL,
        ts bigint NOT NULL,
        payload jsonb NOT NULL
    );
    CREATE UNIQUE INDEX IF NOT EXISTS uq_signal_key
      ON signals(tenant_id,market,symbol,timeframe,ts);
    """)
    op.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id text PRIMARY KEY,
        who text NOT NULL,
        what text NOT NULL,
        prev_hash text,
        this_hash text NOT NULL,
        created_at timestamptz DEFAULT now()
    );
    """)

def downgrade():
    op.execute("DROP TABLE IF EXISTS audit_log;")
    op.execute("DROP TABLE IF EXISTS signals;")
    op.execute("DROP TABLE IF EXISTS runs;")
    op.execute("DROP TABLE IF EXISTS ohlcv;")
