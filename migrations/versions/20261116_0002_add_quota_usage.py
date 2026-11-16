"""add quota usage

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-16 11:18:44.114508

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Counts of free-allowance use per day and per month (app/services/quota.py)."""
    op.create_table('quota_usage',
    sa.Column('period', sa.String(length=5), nullable=False),
    sa.Column('starts', sa.Date(), nullable=False),
    sa.Column('resource', sa.String(length=100), nullable=False),
    sa.Column('pool', sa.String(length=20), nullable=False),
    sa.Column('used', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('period', 'starts', 'resource', 'pool')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('quota_usage')
