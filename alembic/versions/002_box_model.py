"""Box model migration

Revision ID: 002
Revises: 001
Create Date: 2024-01-15 00:00:00.000000

This migration introduces the Box model architecture:
- Creates boxes table for VPS instances
- Creates box_agents table for agents installed in boxes
- Adds new columns to agent_catalog for install scripts
- Removes old deployment tables (clean break)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to agent_catalog
    op.add_column('agent_catalog', sa.Column('install_script_url', sa.String(500), nullable=True))
    op.add_column('agent_catalog', sa.Column('install_command', sa.Text(), nullable=True))
    op.add_column('agent_catalog', sa.Column('tui_command', sa.String(200), nullable=True))

    # Create boxes table
    op.create_table(
        'boxes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('tier', sa.String(20), nullable=False, server_default='basic'),
        sa.Column('droplet_id', sa.String(50), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('region', sa.String(20), nullable=True, server_default='nyc1'),
        sa.Column('status', sa.String(20), nullable=True, server_default='pending'),
        sa.Column('status_message', sa.Text(), nullable=True),
        sa.Column('system_ssh_key_id', sa.String(50), nullable=True),
        sa.Column('system_private_key', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_boxes_user_id'), 'boxes', ['user_id'], unique=False)

    # Create box_agents table
    op.create_table(
        'box_agents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('box_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('instance_name', sa.String(100), nullable=False),
        sa.Column('install_script_url', sa.String(500), nullable=True),
        sa.Column('install_log', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=True, server_default='pending'),
        sa.Column('status_message', sa.Text(), nullable=True),
        sa.Column('config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['box_id'], ['boxes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_box_agents_box_id'), 'box_agents', ['box_id'], unique=False)
    op.create_index(op.f('ix_box_agents_agent_id'), 'box_agents', ['agent_id'], unique=False)

    # Drop old deployment tables (clean break)
    op.drop_table('deployment_config')
    op.drop_table('deployments')

    # Remove deployments relationship column reference in agent_catalog
    # (The relationship was removed from the model, no schema change needed)


def downgrade() -> None:
    # Recreate old deployment tables
    op.create_table(
        'deployments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('droplet_id', sa.String(50), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('ssh_user', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('status_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_catalog.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'deployment_config',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('deployment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('is_secret', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['deployment_id'], ['deployments.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Drop box tables
    op.drop_index(op.f('ix_box_agents_agent_id'), table_name='box_agents')
    op.drop_index(op.f('ix_box_agents_box_id'), table_name='box_agents')
    op.drop_table('box_agents')
    op.drop_index(op.f('ix_boxes_user_id'), table_name='boxes')
    op.drop_table('boxes')

    # Remove new columns from agent_catalog
    op.drop_column('agent_catalog', 'tui_command')
    op.drop_column('agent_catalog', 'install_command')
    op.drop_column('agent_catalog', 'install_script_url')
