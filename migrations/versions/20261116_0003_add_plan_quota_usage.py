"""add plan quota usage

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-16 12:13:35.367096

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Each user's new Plans per UTC day (app/services/plan_quota.py)."""
    op.create_table('plan_quota_usage',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('day', sa.Date(), nullable=False),
    sa.Column('used', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'day')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('plan_quota_usage')
