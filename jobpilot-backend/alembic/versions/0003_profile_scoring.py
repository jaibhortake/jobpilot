"""profile, scores, feedback, feature weights

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"


def upgrade() -> None:
    op.create_table(
        "profile",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("role_keywords", postgresql.JSONB, nullable=False),
        sa.Column("locations", postgresql.JSONB, nullable=False),
        sa.Column("include_remote", sa.Boolean, nullable=False),
        sa.Column("max_experience_years", sa.Integer, nullable=False),
        sa.Column("exclude_title_words", postgresql.JSONB, nullable=False),
        sa.Column("hidden_title_words", postgresql.JSONB, nullable=False),
        sa.CheckConstraint("id = 1"),
    )
    op.create_table(
        "job_scores",
        sa.Column("job_id", sa.BigInteger, sa.ForeignKey("jobs.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("filtered", sa.Boolean, nullable=False),
        sa.Column("reasons", postgresql.JSONB, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "feedback",
        sa.Column("job_id", sa.BigInteger, sa.ForeignKey("jobs.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("value", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("value IN (-1, 1)"),
    )
    op.create_table(
        "feature_weights",
        sa.Column("feature", sa.Text, primary_key=True),
        sa.Column("weight", sa.Float, nullable=False),
    )


def downgrade() -> None:
    for t in ("feature_weights", "feedback", "job_scores", "profile"):
        op.drop_table(t)
