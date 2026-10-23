"""add_phase4_matching_preferences

Revision ID: f2c3d4e5a6b7
Revises: d841747bd855
Create Date: 2026-10-22 10:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2c3d4e5a6b7'
down_revision: Union[str, Sequence[str], None] = 'd841747bd855'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade user_preferences schema to support personalized opportunity matching."""
    op.add_column(
        'user_preferences',
        sa.Column('preferred_locations', sa.JSON(), server_default='[]', nullable=False),
    )
    op.add_column(
        'user_preferences',
        sa.Column('remote_only', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )
    op.add_column(
        'user_preferences',
        sa.Column('skills', sa.JSON(), server_default='[]', nullable=False),
    )
    op.add_column(
        'user_preferences',
        sa.Column('education_level', sa.String(length=128), nullable=True),
    )
    op.add_column(
        'user_preferences',
        sa.Column('graduation_year', sa.Integer(), nullable=True),
    )
    op.add_column(
        'user_preferences',
        sa.Column('eligibility_context', sa.JSON(), server_default='{}', nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user_preferences', 'eligibility_context')
    op.drop_column('user_preferences', 'graduation_year')
    op.drop_column('user_preferences', 'education_level')
    op.drop_column('user_preferences', 'skills')
    op.drop_column('user_preferences', 'remote_only')
    op.drop_column('user_preferences', 'preferred_locations')
