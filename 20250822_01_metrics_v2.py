
"""Create accuracy_metrics and simulated_pnl tables

Revision ID: 20250822_01
Revises: 
Create Date: 2025-08-22

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250822_01'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'accuracy_metrics',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('market', sa.String(), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('timeframe', sa.String(), nullable=False),
        sa.Column('horizon_bars', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('sample_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('hit_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('accuracy', sa.Float(), nullable=False, server_default='0'),
        sa.Column('details', sa.dialects.postgresql.JSONB()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'))
    )
    op.create_unique_constraint('uq_accuracy_key', 'accuracy_metrics',
        ['tenant_id','market','symbol','timeframe','horizon_bars'])
    op.create_index('ix_accuracy_metrics_symbol_tf', 'accuracy_metrics', ['symbol','timeframe'])

    op.create_table(
        'simulated_pnl',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('market', sa.String(), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('timeframe', sa.String(), nullable=False),
        sa.Column('fee_bps', sa.Float(), nullable=False, server_default='10'),
        sa.Column('slippage_bps', sa.Float(), nullable=False, server_default='5'),
        sa.Column('total_pnl', sa.Float(), nullable=False, server_default='0'),
        sa.Column('max_drawdown', sa.Float(), nullable=False, server_default='0'),
        sa.Column('n_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('equity_curve', sa.dialects.postgresql.JSONB()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'))
    )
    op.create_unique_constraint('uq_pnl_key', 'simulated_pnl',
        ['tenant_id','market','symbol','timeframe','fee_bps','slippage_bps'])
    op.create_index('ix_simulated_pnl_symbol_tf', 'simulated_pnl', ['symbol','timeframe'])

def downgrade():
    op.drop_index('ix_simulated_pnl_symbol_tf', table_name='simulated_pnl')
    op.drop_constraint('uq_pnl_key', 'simulated_pnl', type_='unique')
    op.drop_table('simulated_pnl')

    op.drop_index('ix_accuracy_metrics_symbol_tf', table_name='accuracy_metrics')
    op.drop_constraint('uq_accuracy_key', 'accuracy_metrics', type_='unique')
    op.drop_table('accuracy_metrics')
