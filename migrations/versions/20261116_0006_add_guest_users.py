"""add guest users

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-16 15:58:30.041344

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CHECK = "is_guest OR (email IS NOT NULL AND username IS NOT NULL AND hashed_password IS NOT NULL)"


def upgrade() -> None:
    """Guests (#125): users without credentials, held to them unless is_guest."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_guest', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('last_seen_at', sa.DateTime(), nullable=True))
        batch_op.alter_column('username', existing_type=sa.VARCHAR(), nullable=True)
        batch_op.alter_column('email', existing_type=sa.VARCHAR(), nullable=True)
        batch_op.alter_column('hashed_password', existing_type=sa.VARCHAR(), nullable=True)
        batch_op.create_check_constraint('ck_users_account_has_credentials', CHECK)


def downgrade() -> None:
    """Remove guests (accounts can't be without credentials again), then the columns."""
    op.execute(sa.text("DELETE FROM users WHERE is_guest"))
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('ck_users_account_has_credentials', type_='check')
        batch_op.alter_column('hashed_password', existing_type=sa.VARCHAR(), nullable=False)
        batch_op.alter_column('email', existing_type=sa.VARCHAR(), nullable=False)
        batch_op.alter_column('username', existing_type=sa.VARCHAR(), nullable=False)
        batch_op.drop_column('last_seen_at')
        batch_op.drop_column('is_guest')
