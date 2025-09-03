"""auth+core tables: api_keys, subscriptions, signals, scores, backtests, alerts"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250903_01_auth_and_core_tables"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "api_keys",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("tenant_id", sa.String(64), nullable=True, index=True),
        sa.Column("user_email", sa.String(255), nullable=True, index=True),
        sa.Column("plan", sa.String(64), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.BigInteger, nullable=True),  # epoch seconds
        sa.Column("last_used_at", sa.BigInteger, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("customer_id", sa.String(128), nullable=False),
        sa.Column("subscription_id", sa.String(128), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=True, index=True),
        sa.Column("plan", sa.String(64), nullable=True),
        sa.Column("current_period_end", sa.BigInteger, nullable=True),  # epoch seconds
        sa.Column("status", sa.String(64), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_subscriptions_customer", "subscriptions", ["customer_id"])

    op.create_table(
        "signals",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("market", sa.String(32), nullable=False, index=True),
        sa.Column("symbol", sa.String(64), nullable=False, index=True),
        sa.Column("timeframe", sa.String(16), nullable=False, index=True),
        sa.Column("ts", sa.BigInteger, nullable=False, index=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("meta", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "scores",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("market", sa.String(32), nullable=False, index=True),
        sa.Column("symbol", sa.String(64), nullable=False, index=True),
        sa.Column("timeframe", sa.String(16), nullable=False, index=True),
        sa.Column("ts", sa.BigInteger, nullable=False, index=True),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("components", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "backtests",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("strategy", sa.String(128), nullable=False, index=True),
        sa.Column("market", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("period", sa.String(64), nullable=True),
        sa.Column("trades", sa.Integer, nullable=True),
        sa.Column("pnl", sa.Float, nullable=True),
        sa.Column("winrate", sa.Float, nullable=True),
        sa.Column("sharpe", sa.Float, nullable=True),
        sa.Column("stats", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("channel", sa.String(32), nullable=False),  # email|slack|webhook|sms
        sa.Column("destination", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("meta", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

def downgrade():
    op.drop_table("alerts")
    op.drop_table("backtests")
    op.drop_table("scores")
    op.drop_table("signals")
    op.drop_index("ix_subscriptions_customer", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("api_keys")
