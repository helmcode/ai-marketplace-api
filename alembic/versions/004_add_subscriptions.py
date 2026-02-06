"""Add subscriptions table and stripe_customer_id to users

Revision ID: 004
Revises: 003
Create Date: 2026-02-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('box_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('boxes.id'), nullable=True, index=True),
        sa.Column('stripe_customer_id', sa.String(255), nullable=False, index=True),
        sa.Column('stripe_subscription_id', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('stripe_price_id', sa.String(255), nullable=False),
        sa.Column('status', sa.String(30), server_default='active'),
        sa.Column('grace_period_end', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),
    )
    op.add_column('users', sa.Column('stripe_customer_id', sa.String(255), nullable=True))
    op.create_index('ix_users_stripe_customer_id', 'users', ['stripe_customer_id'])


def downgrade() -> None:
    op.drop_index('ix_users_stripe_customer_id', table_name='users')
    op.drop_column('users', 'stripe_customer_id')
    op.drop_table('subscriptions')
