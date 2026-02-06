"""Add cancel_at column to subscriptions

Revision ID: 005
Revises: 004
Create Date: 2026-02-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('subscriptions', sa.Column('cancel_at', sa.DateTime, nullable=True))


def downgrade() -> None:
    op.drop_column('subscriptions', 'cancel_at')
