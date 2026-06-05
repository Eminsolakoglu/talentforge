from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.postgres import Base


def new_id() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(160), unique=True, index=True)
    website: Mapped[str | None] = mapped_column(String(255))

    users: Mapped[list["User"]] = relationship(back_populates="organization")
    job_posts: Mapped[list["JobPost"]] = relationship(back_populates="organization")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="SET NULL"), index=True
    )

    organization: Mapped[Organization | None] = relationship(back_populates="users")
    hr_profile: Mapped["HRProfile | None"] = relationship(back_populates="user")
    candidate_profile: Mapped["CandidateProfile | None"] = relationship(back_populates="user")


class HRProfile(TimestampMixin, Base):
    __tablename__ = "hr_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(120))
    department: Mapped[str | None] = mapped_column(String(120))

    user: Mapped[User] = relationship(back_populates="hr_profile")


class CandidateProfile(TimestampMixin, Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    school: Mapped[str | None] = mapped_column(String(180))
    profession: Mapped[str | None] = mapped_column(String(140), index=True)
    experience_years: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    location: Mapped[str | None] = mapped_column(String(140), index=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    linkedin_url: Mapped[str | None] = mapped_column(String(255))
    portfolio_url: Mapped[str | None] = mapped_column(String(255))
    neo4j_candidate_id: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)

    user: Mapped[User] = relationship(back_populates="candidate_profile")
    applications: Mapped[list["JobApplication"]] = relationship(back_populates="candidate")


class JobPost(TimestampMixin, Base):
    __tablename__ = "job_posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(140), index=True)
    seniority: Mapped[str | None] = mapped_column(String(80), index=True)
    min_experience_years: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    must_have_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    nice_to_have_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="job_posts")
    applications: Mapped[list["JobApplication"]] = relationship(back_populates="job_post")


class SavedSearch(TimestampMixin, Base):
    __tablename__ = "saved_searches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    query_spec: Mapped[dict] = mapped_column(JSON, nullable=False)


class Shortlist(TimestampMixin, Base):
    __tablename__ = "shortlists"
    __table_args__ = (
        UniqueConstraint("job_post_id", "candidate_profile_id", name="uq_shortlists_job_candidate"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    job_post_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("job_posts.id", ondelete="SET NULL"), index=True
    )
    candidate_profile_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("candidate_profiles.id", ondelete="SET NULL"), index=True
    )
    neo4j_candidate_id: Mapped[str | None] = mapped_column(String(120), index=True)
    stage: Mapped[str] = mapped_column(String(60), default="saved", nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)


class JobApplication(TimestampMixin, Base):
    __tablename__ = "job_applications"
    __table_args__ = (
        UniqueConstraint(
            "job_post_id", "candidate_profile_id", name="uq_job_applications_job_candidate"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_post_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_posts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    candidate_profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), default="submitted", index=True, nullable=False)
    match_score: Mapped[float | None] = mapped_column(Float)
    match_breakdown: Mapped[dict | None] = mapped_column(JSON)
    cover_letter: Mapped[str | None] = mapped_column(Text)

    job_post: Mapped[JobPost] = relationship(back_populates="applications")
    candidate: Mapped[CandidateProfile] = relationship(back_populates="applications")


class PasswordResetToken(TimestampMixin, Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
