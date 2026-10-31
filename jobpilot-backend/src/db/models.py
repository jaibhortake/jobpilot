import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class AtsType(enum.StrEnum):
    workday = "workday"
    oracle = "oracle"
    smartrecruiters = "smartrecruiters"
    ashby = "ashby"
    greenhouse = "greenhouse"
    lever = "lever"
    icims = "icims"
    generic = "generic"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    name_key: Mapped[str] = mapped_column(Text, unique=True)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True)  # email domain, user-confirmed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sources: Mapped[list["CareerSource"]] = relationship(
        back_populates="company", cascade="all, delete-orphan", order_by="CareerSource.id"
    )
    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="company", cascade="all, delete-orphan", order_by="Contact.id"
    )


class CareerSource(Base):
    __tablename__ = "career_sources"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(Text, unique=True)
    ats_type: Mapped[AtsType] = mapped_column(SAEnum(AtsType, name="ats_type"))
    ats_config: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_status: Mapped[str] = mapped_column(Text, default="never")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_found: Mapped[int | None] = mapped_column(nullable=True)
    last_kept: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped[Company] = relationship(back_populates="sources")


class Contact(Base):
    """An HR / recruiter email for a company (imported from the sheet or added by hand)."""

    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("company_id", "email"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin: Mapped[str] = mapped_column(Text, default="manual")  # sheet / manual
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped[Company] = relationship(back_populates="contacts")


class JobStatus(enum.StrEnum):
    new = "new"
    shortlisted = "shortlisted"
    materials_ready = "materials_ready"
    applied = "applied"
    interview = "interview"
    offer = "offer"
    rejected = "rejected"
    dismissed = "dismissed"
    closed = "closed"


class CheckRun(Base):
    __tablename__ = "check_runs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("career_sources.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, default="running")  # running/done/failed/cancelled
    phase: Mapped[str] = mapped_column(Text, default="crawling")
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    stats: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("company_id", "external_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("career_sources.id", ondelete="CASCADE"), nullable=True
    )
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    external_id: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_known: Mapped[bool] = mapped_column(Boolean, default=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    missed_checks: Mapped[int] = mapped_column(default=0)
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name="job_status"), default=JobStatus.new
    )
    status_before_close: Mapped[JobStatus | None] = mapped_column(
        SAEnum(JobStatus, name="job_status"), nullable=True
    )
    origin: Mapped[str] = mapped_column(Text, default="check")  # check/url/manual
    ai_score: Mapped[int | None] = mapped_column(nullable=True)  # Qwen's 0-100 judgement
    ai_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    company: Mapped[Company] = relationship()


class JobStatusEvent(Base):
    __tablename__ = "job_status_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    from_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_status: Mapped[str] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(Text, default="system")


class Profile(Base):
    """Single-row search profile (id is always 1)."""

    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    role_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    locations: Mapped[list[str]] = mapped_column(JSON, default=list)
    include_remote: Mapped[bool] = mapped_column(Boolean, default=True)
    max_experience_years: Mapped[int] = mapped_column(default=2)
    exclude_title_words: Mapped[list[str]] = mapped_column(JSON, default=list)
    hidden_title_words: Mapped[list[str]] = mapped_column(JSON, default=list)


class JobScore(Base):
    __tablename__ = "job_scores"

    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    score: Mapped[int] = mapped_column(default=0)
    filtered: Mapped[bool] = mapped_column(Boolean, default=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Feedback(Base):
    __tablename__ = "feedback"

    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    value: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FeatureWeight(Base):
    __tablename__ = "feature_weights"

    feature: Mapped[str] = mapped_column(Text, primary_key=True)
    weight: Mapped[float] = mapped_column()
