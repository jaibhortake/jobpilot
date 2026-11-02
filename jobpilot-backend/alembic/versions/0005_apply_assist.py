"""applicant details, answer bank

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"


def upgrade() -> None:
    op.create_table(
        "applicant",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("details", sa.JSON, nullable=False),
        sa.Column("disabled_sites", sa.JSON, nullable=False),
    )
    op.create_table(
        "answers",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("key", sa.Text, nullable=False, unique=True),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("answers")
    op.drop_table("applicant")
