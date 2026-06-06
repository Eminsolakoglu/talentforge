from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import date

class ExperienceRecord(BaseModel):
    company_name: str
    role_title: str
    start_date: Optional[str] = None          # date → str (daha esnek)
    end_date: Optional[str] = None            # date → str
    is_current: bool = False
    location: Optional[str] = None
    description: Optional[str] = None
    achievements: List[str] = Field(default_factory=list)
    skills_used: List[str] = Field(default_factory=list)
    evidence_text: str = Field(..., description="Kaynak metinden alıntı")
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_text: str = ""

class SkillRecord(BaseModel):
    name: str
    category: Optional[str] = None
    years_experience: Optional[int] = None
    level: Optional[int] = Field(None, ge=1, le=5)
    evidence_text: str
    evidence_text: str = "" 
    confidence: float = 0.8 

class EducationRecord(BaseModel):
    degree: str
    field: str
    institution: str
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    gpa: Optional[float] = None


class ProjectRecord(BaseModel):
    name: str
    description: Optional[str] = None
    role: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    url: Optional[str] = None
    skills_used: List[str] = Field(default_factory=list)
    evidence_text: str = ""
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)

class CVExtraction(BaseModel):
    candidate_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    summary: Optional[str] = None
    experiences: List[ExperienceRecord] = Field(default_factory=list)
    skills: List[SkillRecord] = Field(default_factory=list)
    educations: List[EducationRecord] = Field(default_factory=list)
    projects: List[ProjectRecord] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)

    @field_validator(
        "experiences",
        "skills",
        "educations",
        "projects",
        "languages",
        "certifications",
        mode="before",
    )
    @classmethod
    def _none_to_empty_list(cls, value):
        return [] if value is None else value
