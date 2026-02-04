"""Add user_ssh_synced to boxes

Revision ID: 003
Revises: 002
Create Date: 2025-02-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('boxes', sa.Column('user_ssh_synced', sa.String(1), nullable=True, server_default='0'))


def downgrade() -> None:
    op.drop_column('boxes', 'user_ssh_synced')
