"""Add last_canvas_access

Revision ID: ab2e5d7e05e8
Revises: c0025f85a371
Create Date: 2025-12-04 11:24:44.987577

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab2e5d7e05e8'
down_revision: Union[str, None] = 'c0025f85a371'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add last_canvas_access column to accelerate_course_progress
    op.add_column(
        'accelerate_course_progress',
        sa.Column('last_canvas_access', sa.DateTime(timezone=False), nullable=True)
    )


def downgrade() -> None:
    # Drop column
    op.drop_column('accelerate_course_progress', 'last_canvas_access')
    