"""initial app schema

Revision ID: 20260531_0001
Revises:
Create Date: 2026-05-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260531_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("domain", sa.String(length=160), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain"),
    )
    op.create_index(op.f("ix_organizations_domain"), "organizations", ["domain"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_organization_id"), "users", ["organization_id"], unique=False)
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)

    op.create_table(
        "candidate_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("school", sa.String(length=180), nullable=True),
        sa.Column("profession", sa.String(length=140), nullable=True),
        sa.Column("experience_years", sa.Integer(), nullable=False),
        sa.Column("location", sa.String(length=140), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("linkedin_url", sa.String(length=255), nullable=True),
        sa.Column("portfolio_url", sa.String(length=255), nullable=True),
        sa.Column("neo4j_candidate_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_candidate_profiles_location"), "candidate_profiles", ["location"], unique=False)
    op.create_index(op.f("ix_candidate_profiles_neo4j_candidate_id"), "candidate_profiles", ["neo4j_candidate_id"], unique=True)
    op.create_index(op.f("ix_candidate_profiles_profession"), "candidate_profiles", ["profession"], unique=False)

    op.create_table(
        "hr_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=True),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "job_posts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=140), nullable=True),
        sa.Column("seniority", sa.String(length=80), nullable=True),
        sa.Column("min_experience_years", sa.Integer(), nullable=False),
        sa.Column("must_have_skills", sa.JSON(), nullable=False),
        sa.Column("nice_to_have_skills", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_posts_created_by_user_id"), "job_posts", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_job_posts_location"), "job_posts", ["location"], unique=False)
    op.create_index(op.f("ix_job_posts_organization_id"), "job_posts", ["organization_id"], unique=False)
    op.create_index(op.f("ix_job_posts_seniority"), "job_posts", ["seniority"], unique=False)
    op.create_index(op.f("ix_job_posts_status"), "job_posts", ["status"], unique=False)

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_password_reset_tokens_user_id"), "password_reset_tokens", ["user_id"], unique=False)

    op.create_table(
        "saved_searches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("query_spec", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_saved_searches_organization_id"), "saved_searches", ["organization_id"], unique=False)
    op.create_index(op.f("ix_saved_searches_user_id"), "saved_searches", ["user_id"], unique=False)

    op.create_table(
        "job_applications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_post_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_profile_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("match_breakdown", sa.JSON(), nullable=True),
        sa.Column("cover_letter", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_profile_id"], ["candidate_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_post_id"], ["job_posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_post_id", "candidate_profile_id", name="uq_job_applications_job_candidate"),
    )
    op.create_index(op.f("ix_job_applications_candidate_profile_id"), "job_applications", ["candidate_profile_id"], unique=False)
    op.create_index(op.f("ix_job_applications_job_post_id"), "job_applications", ["job_post_id"], unique=False)
    op.create_index(op.f("ix_job_applications_status"), "job_applications", ["status"], unique=False)

    op.create_table(
        "shortlists",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("job_post_id", sa.String(length=36), nullable=True),
        sa.Column("candidate_profile_id", sa.String(length=36), nullable=True),
        sa.Column("neo4j_candidate_id", sa.String(length=120), nullable=True),
        sa.Column("stage", sa.String(length=60), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_profile_id"], ["candidate_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_post_id"], ["job_posts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_post_id", "candidate_profile_id", name="uq_shortlists_job_candidate"),
    )
    op.create_index(op.f("ix_shortlists_candidate_profile_id"), "shortlists", ["candidate_profile_id"], unique=False)
    op.create_index(op.f("ix_shortlists_job_post_id"), "shortlists", ["job_post_id"], unique=False)
    op.create_index(op.f("ix_shortlists_neo4j_candidate_id"), "shortlists", ["neo4j_candidate_id"], unique=False)
    op.create_index(op.f("ix_shortlists_organization_id"), "shortlists", ["organization_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_shortlists_organization_id"), table_name="shortlists")
    op.drop_index(op.f("ix_shortlists_neo4j_candidate_id"), table_name="shortlists")
    op.drop_index(op.f("ix_shortlists_job_post_id"), table_name="shortlists")
    op.drop_index(op.f("ix_shortlists_candidate_profile_id"), table_name="shortlists")
    op.drop_table("shortlists")
    op.drop_index(op.f("ix_job_applications_status"), table_name="job_applications")
    op.drop_index(op.f("ix_job_applications_job_post_id"), table_name="job_applications")
    op.drop_index(op.f("ix_job_applications_candidate_profile_id"), table_name="job_applications")
    op.drop_table("job_applications")
    op.drop_index(op.f("ix_saved_searches_user_id"), table_name="saved_searches")
    op.drop_index(op.f("ix_saved_searches_organization_id"), table_name="saved_searches")
    op.drop_table("saved_searches")
    op.drop_index(op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index(op.f("ix_job_posts_status"), table_name="job_posts")
    op.drop_index(op.f("ix_job_posts_seniority"), table_name="job_posts")
    op.drop_index(op.f("ix_job_posts_organization_id"), table_name="job_posts")
    op.drop_index(op.f("ix_job_posts_location"), table_name="job_posts")
    op.drop_index(op.f("ix_job_posts_created_by_user_id"), table_name="job_posts")
    op.drop_table("job_posts")
    op.drop_table("hr_profiles")
    op.drop_index(op.f("ix_candidate_profiles_profession"), table_name="candidate_profiles")
    op.drop_index(op.f("ix_candidate_profiles_neo4j_candidate_id"), table_name="candidate_profiles")
    op.drop_index(op.f("ix_candidate_profiles_location"), table_name="candidate_profiles")
    op.drop_table("candidate_profiles")
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_index(op.f("ix_users_organization_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_organizations_domain"), table_name="organizations")
    op.drop_table("organizations")
