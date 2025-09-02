"""add ts column to signals and unique constraint

Revision ID: 20250825_02
Revises: 42f3a67efccc
Create Date: 2025-08-25
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250825_02"
down_revision = "42f3a67efccc"
branch_labels = None
depends_on = None


def upgrade():
    # 1) adicionar coluna ts (temporariamente com default para não rebentar se já houver linhas)
    op.add_column(
        "signals",
        sa.Column("ts", sa.BigInteger(), nullable=True, server_default=sa.text("0")),
    )

    # 2) remover default e forçar NOT NULL
    with op.batch_alter_table("signals") as batch_op:
        batch_op.alter_column("ts", server_default=None)
        batch_op.alter_column("ts", nullable=False)

    # 3) índices úteis (se ainda não existirem)
    op.create_index(
        "ix_signals_tenant_market_symbol_timeframe_ts",
        "signals",
        ["tenant_id", "market", "symbol", "timeframe", "ts"],
        unique=False,
    )

    # 4) constraint de unicidade no composto
    op.create_unique_constraint(
        "uq_signals_tenant_market_symbol_timeframe_ts",
        "signals",
        ["tenant_id", "market", "symbol", "timeframe", "ts"],
    )


def downgrade():
    # desfazer na ordem inversa
    op.drop_constraint(
        "uq_signals_tenant_market_symbol_timeframe_ts", "signals", type_="unique"
    )
    op.drop_index("ix_signals_tenant_market_symbol_timeframe_ts", table_name="signals")
    op.drop_column("signals", "ts")
