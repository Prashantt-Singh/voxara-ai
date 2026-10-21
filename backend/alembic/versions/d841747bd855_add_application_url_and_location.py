"""add_application_url_and_location

Revision ID: d841747bd855
Revises: df9beaa4ce7d
Create Date: 2026-10-20 01:13:45.445415

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd841747bd855'
down_revision: Union[str, Sequence[str], None] = 'df9beaa4ce7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('opportunities', sa.Column('application_url', sa.Text(), nullable=True))
    op.add_column('opportunities', sa.Column('location', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('opportunities', 'location')
    op.drop_column('opportunities', 'application_url')
