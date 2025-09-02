"""merge heads"""

from alembic import op
import sqlalchemy as sa

# replace these with your two head IDs (shown by `alembic heads`)
revision = "merge_heads_0001"
down_revision = ("20250825_02", "20250827_idx_recent")
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass
