"""company domain, job AI match

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade() -> None:
    op.add_column("companies", sa.Column("domain", sa.Text))
    op.add_column("jobs", sa.Column("ai_score", sa.Integer))
    op.add_column("jobs", sa.Column("ai_reason", sa.Text))


def downgrade() -> None:
    op.drop_column("jobs", "ai_reason")
    op.drop_column("jobs", "ai_score")
    op.drop_column("companies", "domain")
