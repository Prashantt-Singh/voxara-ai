"""initial_multiuser_schema

Revision ID: df9beaa4ce7d
Revises: 
Create Date: 2026-10-20 00:33:59.235350

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df9beaa4ce7d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema for multi-user PostgreSQL (Neon/Supabase)."""
    bind = op.get_bind()
    existing_tables = set()
    if bind is not None:
        try:
            inspector = sa.inspect(bind)
            existing_tables = set(inspector.get_table_names())
        except Exception:
            existing_tables = set()

    # 1. Users table
    if 'users' not in existing_tables:
        op.create_table(
            'users',
            sa.Column('id', sa.String(length=64), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=True),
            sa.Column('name', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
        )
        op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. Opportunities table (shared central catalog)
    if 'opportunities' not in existing_tables:
        op.create_table(
            'opportunities',
            sa.Column('id', sa.String(length=64), nullable=False),
            sa.Column('title', sa.String(length=512), nullable=False),
            sa.Column('organization', sa.String(length=255), nullable=False),
            sa.Column('type', sa.String(length=64), nullable=False),
            sa.Column('source_url', sa.Text(), nullable=False),
            sa.Column('source_name', sa.String(length=128), nullable=False),
            sa.Column('content_hash', sa.String(length=64), nullable=False),
            sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('eligibility', sa.Text(), nullable=True),
            sa.Column('requirements', sa.JSON(), nullable=False),
            sa.Column('prize_or_salary', sa.String(length=255), nullable=True),
            sa.Column('verified_status', sa.String(length=32), nullable=False),
            sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('discovered_at', sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_opportunities'))
        )
        op.create_index(op.f('ix_opportunities_content_hash'), 'opportunities', ['content_hash'], unique=True)
        op.create_index(op.f('ix_opportunities_deadline'), 'opportunities', ['deadline'], unique=False)
        op.create_index(op.f('ix_opportunities_discovered_at'), 'opportunities', ['discovered_at'], unique=False)
        op.create_index(op.f('ix_opportunities_type'), 'opportunities', ['type'], unique=False)

    # 3. User Preferences table
    if 'user_preferences' not in existing_tables:
        op.create_table(
            'user_preferences',
            sa.Column('id', sa.String(length=64), nullable=False),
            sa.Column('user_id', sa.String(length=64), nullable=False),
            sa.Column('preferred_types', sa.JSON(), nullable=False),
            sa.Column('target_roles', sa.JSON(), nullable=False),
            sa.Column('domains', sa.JSON(), nullable=False),
            sa.Column('min_match_score', sa.Float(), nullable=False),
            sa.Column('notifications_enabled', sa.Boolean(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_preferences_user_id_users'), ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_user_preferences')),
            sa.UniqueConstraint('user_id', name=op.f('uq_user_preferences_user_id'))
        )
        op.create_index(op.f('ix_user_preferences_user_id'), 'user_preferences', ['user_id'], unique=True)

    # 4. Saved Opportunities table (user-specific application pipeline)
    if 'saved_opportunities' not in existing_tables:
        op.create_table(
            'saved_opportunities',
            sa.Column('id', sa.String(length=64), nullable=False),
            sa.Column('user_id', sa.String(length=64), nullable=False),
            sa.Column('opportunity_id', sa.String(length=64), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('match_score', sa.Float(), nullable=False),
            sa.Column('match_reason', sa.Text(), nullable=True),
            sa.Column('saved_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], name=op.f('fk_saved_opportunities_opportunity_id_opportunities'), ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_saved_opportunities_user_id_users'), ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_saved_opportunities')),
            sa.UniqueConstraint('user_id', 'opportunity_id', name='uq_user_opportunity')
        )
        op.create_index('ix_saved_opp_user_status', 'saved_opportunities', ['user_id', 'status'], unique=False)
        op.create_index(op.f('ix_saved_opportunities_opportunity_id'), 'saved_opportunities', ['opportunity_id'], unique=False)
        op.create_index(op.f('ix_saved_opportunities_user_id'), 'saved_opportunities', ['user_id'], unique=False)

    # 5. Notifications table (user-specific alert queue)
    if 'notifications' not in existing_tables:
        op.create_table(
            'notifications',
            sa.Column('id', sa.String(length=64), nullable=False),
            sa.Column('user_id', sa.String(length=64), nullable=False),
            sa.Column('opportunity_id', sa.String(length=64), nullable=True),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('spoken_summary', sa.Text(), nullable=True),
            sa.Column('type', sa.String(length=64), nullable=False),
            sa.Column('priority', sa.String(length=32), nullable=False),
            sa.Column('is_read', sa.Boolean(), nullable=False),
            sa.Column('content_hash', sa.String(length=64), nullable=False),
            sa.Column('requires_confirmation', sa.Boolean(), nullable=False),
            sa.Column('confirmation_token', sa.String(length=64), nullable=True),
            sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], name=op.f('fk_notifications_opportunity_id_opportunities'), ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notifications_user_id_users'), ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications'))
        )
        op.create_index(op.f('ix_notifications_content_hash'), 'notifications', ['content_hash'], unique=True)
        op.create_index(op.f('ix_notifications_opportunity_id'), 'notifications', ['opportunity_id'], unique=False)
        op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
        op.create_index('ix_notifications_user_read', 'notifications', ['user_id', 'is_read'], unique=False)

    # 6. Workflow Executions table (telemetry)
    if 'workflow_executions' not in existing_tables:
        op.create_table(
            'workflow_executions',
            sa.Column('execution_id', sa.String(length=64), nullable=False),
            sa.Column('user_id', sa.String(length=64), nullable=True),
            sa.Column('workflow_type', sa.String(length=64), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False),
            sa.Column('task', sa.Text(), nullable=False),
            sa.Column('input_data', sa.JSON(), nullable=True),
            sa.Column('result', sa.JSON(), nullable=True),
            sa.Column('error', sa.Text(), nullable=True),
            sa.Column('events', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_workflow_executions_user_id_users'), ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('execution_id', name=op.f('pk_workflow_executions'))
        )
        op.create_index(op.f('ix_workflow_executions_user_id'), 'workflow_executions', ['user_id'], unique=False)
        op.create_index(op.f('ix_workflow_executions_workflow_type'), 'workflow_executions', ['workflow_type'], unique=False)

    # Clean legacy prototype tables if present
    if 'research_items' in existing_tables:
        op.drop_table('research_items')
    if 'research_topics' in existing_tables:
        op.drop_table('research_topics')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('workflow_executions')
    op.drop_table('notifications')
    op.drop_table('saved_opportunities')
    op.drop_table('user_preferences')
    op.drop_table('opportunities')
    op.drop_table('users')
