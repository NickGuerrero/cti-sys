"""Add launch & ca_region to students; drop details from ethnicities

Revision ID: 234eb1d89dec
Revises: 
Create Date: 2025-05-21 11:03:56.946044

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '234eb1d89dec'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # update students table to add launch and ca_region columns
    op.add_column('students', sa.Column('launch', sa.Boolean(), nullable=True))
    op.add_column('students', sa.Column('ca_region', sa.String(), nullable=True))
    # update ethnicities table to drop details column
    op.drop_column('ethnicities', 'details')


def downgrade() -> None:
    # downgrade students table to remove launch and ca_region columns
    op.drop_column('students', 'ca_region')
    op.drop_column('students', 'launch')
    # downgrade to add details column back
    op.add_column('ethnicities', sa.Column('details', sa.VARCHAR(), autoincrement=False, nullable=True))
