"""companies, career sources, contacts

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None

ATS = ("workday", "oracle", "smartrecruiters", "ashby", "greenhouse", "lever", "icims", "generic")


def upgrade() -> None:
    ident = sa.Identity(always=True)
    op.create_table(
        "companies",
        sa.Column("id", sa.BigInteger, ident, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("name_key", sa.Text, nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "career_sources",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("company_id", sa.BigInteger, sa.ForeignKey("companies.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("url", sa.Text, nullable=False, unique=True),
        sa.Column("ats_type", postgresql.ENUM(*ATS, name="ats_type"), nullable=False),
        sa.Column("ats_config", postgresql.JSONB, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "contacts",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("company_id", sa.BigInteger, sa.ForeignKey("companies.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("name", sa.Text),
        sa.Column("origin", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "email"),
    )


def downgrade() -> None:
    op.drop_table("contacts")
    op.drop_table("career_sources")
    op.drop_table("companies")
    op.execute("DROP TYPE IF EXISTS ats_type CASCADE")
