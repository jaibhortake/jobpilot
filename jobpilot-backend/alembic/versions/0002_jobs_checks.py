"""jobs, check runs, status events

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"

STATUSES = ("new", "shortlisted", "materials_ready", "applied", "interview", "offer",
            "rejected", "dismissed", "closed")


def _status() -> postgresql.ENUM:
    return postgresql.ENUM(*STATUSES, name="job_status", create_type=False)


def upgrade() -> None:
    postgresql.ENUM(*STATUSES, name="job_status").create(op.get_bind())
    ts = sa.DateTime(timezone=True)
    for col in (
        sa.Column("last_check_at", ts),
        sa.Column("last_success_at", ts),
        sa.Column("last_status", sa.Text, nullable=False, server_default="never"),
        sa.Column("last_error", sa.Text),
        sa.Column("last_found", sa.Integer),
        sa.Column("last_kept", sa.Integer),
    ):
        op.add_column("career_sources", col)

    op.create_table(
        "check_runs",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("source_id", sa.BigInteger,
                  sa.ForeignKey("career_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", ts, server_default=sa.func.now()),
        sa.Column("finished_at", ts),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("phase", sa.Text, nullable=False),
        sa.Column("cancel_requested", sa.Boolean, nullable=False),
        sa.Column("stats", postgresql.JSONB, nullable=False),
        sa.Column("error", sa.Text),
    )
    op.create_index("uq_check_running", "check_runs", ["source_id"], unique=True,
                    postgresql_where=sa.text("status = 'running'"))

    op.create_table(
        "jobs",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("source_id", sa.BigInteger,
                  sa.ForeignKey("career_sources.id", ondelete="CASCADE")),
        sa.Column("company_id", sa.BigInteger,
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("location", sa.Text),
        sa.Column("remote", sa.Boolean, nullable=False),
        sa.Column("country", sa.Text),
        sa.Column("url", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("description_source", sa.Text),
        sa.Column("posted_at", ts),
        sa.Column("posted_text", sa.Text),
        sa.Column("date_known", sa.Boolean, nullable=False),
        sa.Column("first_seen_at", ts, server_default=sa.func.now()),
        sa.Column("last_seen_at", ts, server_default=sa.func.now()),
        sa.Column("missed_checks", sa.Integer, nullable=False),
        sa.Column("status", _status(), nullable=False),
        sa.Column("status_before_close", _status()),
        sa.Column("origin", sa.Text, nullable=False),
        sa.UniqueConstraint("company_id", "external_id"),
    )
    op.create_table(
        "job_status_events",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("job_id", sa.BigInteger,
                  sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.Text),
        sa.Column("to_status", sa.Text, nullable=False),
        sa.Column("at", ts, server_default=sa.func.now()),
        sa.Column("note", sa.Text),
        sa.Column("actor", sa.Text, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("job_status_events")
    op.drop_table("jobs")
    op.drop_index("uq_check_running", table_name="check_runs")
    op.drop_table("check_runs")
    for c in ("last_check_at", "last_success_at", "last_status", "last_error", "last_found",
              "last_kept"):
        op.drop_column("career_sources", c)
    op.execute("DROP TYPE IF EXISTS job_status CASCADE")
