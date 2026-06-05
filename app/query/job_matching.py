from typing import Any

from app.models.postgres import JobPost
from app.query.matcher import CandidateMatcher
from app.schemas.query import QuerySpec, Seniority


def job_post_to_query_spec(job_post: JobPost) -> QuerySpec:
    seniority = None
    if job_post.seniority:
        try:
            seniority = Seniority(job_post.seniority.lower())
        except ValueError:
            seniority = None

    locations = [job_post.location] if job_post.location else []
    return QuerySpec(
        title=job_post.title,
        seniority=seniority,
        must_have_skills=job_post.must_have_skills or [],
        nice_to_have_skills=job_post.nice_to_have_skills or [],
        min_experience_years=job_post.min_experience_years,
        locations=locations,
        free_text=job_post.description,
    )


def match_candidates_for_job(
    matcher: CandidateMatcher,
    job_post: JobPost,
    limit: int = 25,
    min_score: float = 18.0,
) -> list[dict[str, Any]]:
    query = job_post_to_query_spec(job_post)
    return matcher.search(
        query,
        limit=limit,
        min_score=min_score,
        apply_hard_gate=False,
    )
