"""unique api_keys + subscriptions

Revision ID: 7d7e1e7a4c1a
Revises: 
Create Date: 2025-09-03 10:00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "7d7e1e7a4c1a"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ensure tables exist (safe if already created)
    op.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
      id SERIAL PRIMARY KEY,
      customer_id TEXT NOT NULL,
      subscription_id TEXT NOT NULL,
      email TEXT NOT NULL,
      plan TEXT NOT NULL DEFAULT 'pro',
      status TEXT NOT NULL DEFAULT 'active',
      current_period_end BIGINT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)
    op.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
      id SERIAL PRIMARY KEY,
      user_email TEXT NOT NULL,
      plan TEXT NOT NULL DEFAULT 'pro',
      key TEXT NOT NULL UNIQUE,
      active BOOLEAN NOT NULL DEFAULT TRUE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)

    # unique subscription_id
    op.execute("""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname='uq_subscriptions_subscription_id'
      ) THEN
        ALTER TABLE subscriptions
          ADD CONSTRAINT uq_subscriptions_subscription_id
          UNIQUE (subscription_id);
      END IF;
    END$$;
    """)

    # one key per (user_email, plan)
    op.execute("""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname='uq_api_keys_user_plan'
      ) THEN
        ALTER TABLE api_keys
          ADD CONSTRAINT uq_api_keys_user_plan
          UNIQUE (user_email, plan);
      END IF;
    END$$;
    """)

    # keep an index on api_keys.key for lookups (unique already creates one, but harmless if not exists)
    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS ix_api_keys_key ON api_keys(key);
    """)


def downgrade():
    op.execute("""
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname='uq_api_keys_user_plan') THEN
        ALTER TABLE api_keys DROP CONSTRAINT uq_api_keys_user_plan;
      END IF;
    END$$;
    """)
    op.execute("""
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname='uq_subscriptions_subscription_id') THEN
        ALTER TABLE subscriptions DROP CONSTRAINT uq_subscriptions_subscription_id;
      END IF;
    END$$;
    """)
    op.execute("DROP INDEX IF EXISTS ix_api_keys_key;")
