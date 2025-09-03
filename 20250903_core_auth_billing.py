"""core tables: api_keys, subscriptions, signals, scores, backtests, alerts"""

from alembic import op
from textwrap import dedent

# Alembic identifiers
revision = "20250903_core_auth_billing"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(dedent("""
    CREATE TABLE IF NOT EXISTS api_keys(
      key                TEXT PRIMARY KEY,
      user_email         TEXT,
      tenant_id          TEXT DEFAULT 't1' NOT NULL,
      stripe_customer_id TEXT UNIQUE,
      status             TEXT DEFAULT 'active' NOT NULL, -- active|revoked|expired|pending
      plan               TEXT,
      created_at         TIMESTAMPTZ DEFAULT NOW() NOT NULL,
      updated_at         TIMESTAMPTZ DEFAULT NOW() NOT NULL,
      last_used_at       TIMESTAMPTZ,
      expires_at         TIMESTAMPTZ,
      metadata           JSONB DEFAULT '{}'::jsonb
    );
    CREATE INDEX IF NOT EXISTS idx_api_keys_status ON api_keys(status);
    CREATE INDEX IF NOT EXISTS idx_api_keys_expires ON api_keys(expires_at);

    CREATE TABLE IF NOT EXISTS subscriptions(
      id                      BIGSERIAL PRIMARY KEY,
      tenant_id               TEXT DEFAULT 't1' NOT NULL,
      user_email              TEXT,
      stripe_customer_id      TEXT UNIQUE,
      stripe_subscription_id  TEXT UNIQUE,
      status                  TEXT, -- trialing|active|past_due|canceled|unpaid
      plan                    TEXT,
      current_period_end      TIMESTAMPTZ,
      created_at              TIMESTAMPTZ DEFAULT NOW() NOT NULL,
      updated_at              TIMESTAMPTZ DEFAULT NOW() NOT NULL,
      metadata                JSONB DEFAULT '{}'::jsonb
    );
    CREATE INDEX IF NOT EXISTS idx_subs_status ON subscriptions(status);

    CREATE TABLE IF NOT EXISTS signals(
      tenant_id   TEXT NOT NULL,
      market      TEXT NOT NULL,
      symbol      TEXT NOT NULL,
      timeframe   TEXT NOT NULL,
      ts          BIGINT NOT NULL,
      name        TEXT   NOT NULL,  -- e.g. rsi_cross, macd, etc
      value       DOUBLE PRECISION,
      extra       JSONB DEFAULT '{}'::jsonb,
      PRIMARY KEY(tenant_id,market,symbol,timeframe,ts,name)
    );
    CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol, timeframe);

    CREATE TABLE IF NOT EXISTS scores(
      tenant_id   TEXT NOT NULL,
      market      TEXT NOT NULL,
      symbol      TEXT NOT NULL,
      timeframe   TEXT NOT NULL,
      ts          BIGINT NOT NULL,
      score       DOUBLE PRECISION NOT NULL,
      components  JSONB DEFAULT '{}'::jsonb,
      PRIMARY KEY(tenant_id,market,symbol,timeframe,ts)
    );
    CREATE INDEX IF NOT EXISTS idx_scores_symbol ON scores(symbol, timeframe);

    CREATE TABLE IF NOT EXISTS backtests(
      id           BIGSERIAL PRIMARY KEY,
      tenant_id    TEXT DEFAULT 't1' NOT NULL,
      strategy     TEXT NOT NULL,
      parameters   JSONB DEFAULT '{}'::jsonb,
      metrics      JSONB DEFAULT '{}'::jsonb,
      started_at   TIMESTAMPTZ DEFAULT NOW() NOT NULL,
      finished_at  TIMESTAMPTZ
    );

    CREATE TABLE IF NOT EXISTS alerts(
      id           BIGSERIAL PRIMARY KEY,
      tenant_id    TEXT DEFAULT 't1' NOT NULL,
      user_email   TEXT,
      rule         JSONB NOT NULL,      -- e.g. {"type":"rsi_cross","gt":70}
      channel      TEXT,                -- email|webhook|slack|sms
      is_active    BOOLEAN DEFAULT TRUE,
      created_at   TIMESTAMPTZ DEFAULT NOW() NOT NULL,
      last_fired   TIMESTAMPTZ
    );
    """))


def downgrade():
    op.execute("""
    DROP TABLE IF EXISTS alerts;
    DROP TABLE IF EXISTS backtests;
    DROP TABLE IF EXISTS scores;
    DROP TABLE IF EXISTS signals;
    DROP TABLE IF EXISTS subscriptions;
    DROP TABLE IF EXISTS api_keys;
    """)
