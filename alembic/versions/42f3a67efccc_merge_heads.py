"""merge heads

Revision ID: 42f3a67efccc
Revises: 20250825_01, 411bc42f845c
Create Date: 2025-08-25 11:56:39.099158

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '42f3a67efccc'
down_revision: Union[str, Sequence[str], None] = ('20250825_01', '411bc42f845c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
