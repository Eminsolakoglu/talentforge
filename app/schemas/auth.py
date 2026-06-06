from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    role: str = Field(pattern="^(hr|candidate)$")
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    company_name: str | None = None
    company_email: EmailStr | None = None
    position: str | None = None
    school: str | None = None
    profession: str | None = None
    experience_years: int = Field(default=0, ge=0, le=50)
    location: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class JobCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(min_length=2)
    location: str | None = None
    seniority: str | None = None
    min_experience_years: int = Field(default=0, ge=0, le=50)
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    status: str = "published"


class ApplicationCreateRequest(BaseModel):
    cover_letter: str | None = None


class SavedSearchCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    query_spec: dict = Field(default_factory=dict)


class ShortlistCreateRequest(BaseModel):
    neo4j_candidate_id: str = Field(min_length=1, max_length=120)
    candidate_name: str | None = None
    score: float | None = None
    notes: str | None = None
