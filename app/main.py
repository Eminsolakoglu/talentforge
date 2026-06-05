from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path
import logging
import tempfile
import os
import hashlib
import mimetypes
from typing import List, Dict
from jose import JWTError, jwt
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.storage import upload_cv as r2_upload, download_cv as r2_download

from app.core.config import get_settings
from app.core.database import get_neo4j_driver, close_neo4j_driver
from app.core.postgres import get_db
from app.core.security import ALGORITHM, create_access_token, hash_password, verify_password
from app.extraction.pipeline import CVProcessingPipeline
from app.models.postgres import (
    CandidateProfile,
    HRProfile,
    JobApplication,
    JobPost,
    Organization,
    User,
)
from app.schemas.auth import (
    ApplicationCreateRequest,
    JobCreateRequest,
    LoginRequest,
    RegisterRequest,
)
from app.schemas.query import QuerySpec
from app.query.matcher import CandidateMatcher

settings = get_settings()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pipeline: CVProcessingPipeline | None = None
matcher: CandidateMatcher | None = None
security = HTTPBearer()


def get_pipeline() -> CVProcessingPipeline:
    global pipeline
    if pipeline is None:
        pipeline = CVProcessingPipeline()
    return pipeline


def get_matcher() -> CandidateMatcher:
    global matcher
    if matcher is None:
        matcher = CandidateMatcher(get_neo4j_driver())
    return matcher

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 TalentForge başlatılıyor...")
    try:
        get_neo4j_driver()
        logger.info("Neo4j baglantisi hazir")
    except Exception as e:
        logger.warning(f"Neo4j hazir degil; PostgreSQL/API akislari calismaya devam edecek: {e}")
    logger.info("✅ Neo4j bağlantısı hazır")
    yield
    close_neo4j_driver()
    logger.info("👋 TalentForge kapatılıyor...")

app = FastAPI(
    title="TalentForge",
    description="LLM-Driven Knowledge Graph for AI-Powered HR Candidate Matching System",
    version="0.1.0",
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/ui", StaticFiles(directory="frontend", html=True), name="ui")


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request, exc):
    logger.error(f"Database error: {exc}")
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "PostgreSQL baglantisi zaman asimina dustu. Supabase direct connection "
                "yerine pooler connection string kullanman gerekebilir."
            )
        },
    )


def serialize_user(user: User) -> dict:
    profile = None
    if user.role == "hr" and user.hr_profile:
        profile = {
            "title": user.hr_profile.title,
            "department": user.hr_profile.department,
        }
    if user.role == "candidate" and user.candidate_profile:
        profile = {
            "school": user.candidate_profile.school,
            "profession": user.candidate_profile.profession,
            "experience_years": user.candidate_profile.experience_years,
            "location": user.candidate_profile.location,
            "neo4j_candidate_id": user.candidate_profile.neo4j_candidate_id,
        }

    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "status": user.status,
        "organization": {
            "id": user.organization.id,
            "name": user.organization.name,
            "domain": user.organization.domain,
        }
        if user.organization
        else None,
        "profile": profile,
    }


def serialize_job(job: JobPost, application: JobApplication | None = None) -> dict:
    return {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "location": job.location,
        "seniority": job.seniority,
        "min_experience_years": job.min_experience_years,
        "must_have_skills": job.must_have_skills,
        "nice_to_have_skills": job.nice_to_have_skills,
        "status": job.status,
        "organization": job.organization.name if job.organization else None,
        "application": serialize_application(application) if application else None,
    }


def serialize_application(application: JobApplication) -> dict:
    return {
        "id": application.id,
        "status": application.status,
        "match_score": application.match_score,
        "match_breakdown": application.match_breakdown,
        "cover_letter": application.cover_letter,
        "job": {
            "id": application.job_post.id,
            "title": application.job_post.title,
            "organization": application.job_post.organization.name
            if application.job_post.organization
            else None,
            "location": application.job_post.location,
        },
    }


def _email_domain(email: str) -> str:
    return email.split("@", 1)[1].lower()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Oturum gecersiz") from exc

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kullanici bulunamadi")
    return user


def require_role(user: User, role: str) -> None:
    if user.role != role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu islem icin yetkin yok")


def _compute_file_hash(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_local_cv_by_hash(file_hash: str | None) -> Path | None:
    if not file_hash:
        return None
    cv_dir = Path("data/cvs")
    if not cv_dir.exists():
        return None
    for file_path in sorted([*cv_dir.glob("*.pdf"), *cv_dir.glob("*.docx")]):
        try:
            if _compute_file_hash(file_path) == file_hash:
                return file_path
        except OSError:
            continue
    return None

@app.get("/")
async def root():
    return {
        "message": "🚀 TalentForge API is running successfully!",
        "status": "healthy",
        "environment": settings.ENV,
        "docs_url": "/docs",
        "neo4j": "Connected ✅"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "neo4j": "connected",
        "environment": settings.ENV
    }


@app.post("/auth/register")
async def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = str(payload.company_email or payload.email).lower() if payload.role == "hr" else str(payload.email).lower()
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(status_code=409, detail="Bu e-posta ile kayitli kullanici var")

    organization = None
    if payload.role == "hr":
        company_email = str(payload.company_email or payload.email).lower()
        domain = _email_domain(company_email)
        organization = db.query(Organization).filter(Organization.domain == domain).first()
        if not organization:
            organization = Organization(
                name=payload.company_name or domain,
                domain=domain,
            )
            db.add(organization)
            db.flush()

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        organization_id=organization.id if organization else None,
    )
    db.add(user)
    db.flush()

    if payload.role == "hr":
        db.add(HRProfile(user_id=user.id, title=payload.position))
    else:
        db.add(
            CandidateProfile(
                user_id=user.id,
                school=payload.school,
                profession=payload.profession,
                experience_years=payload.experience_years,
                location=payload.location,
            )
        )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Kayit olusturulamadi") from exc

    db.refresh(user)
    token = create_access_token(user.id, {"role": user.role})
    return {"access_token": token, "token_type": "bearer", "user": serialize_user(user)}


@app.post("/auth/login")
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="E-posta veya sifre hatali")

    token = create_access_token(user.id, {"role": user.role})
    return {"access_token": token, "token_type": "bearer", "user": serialize_user(user)}


@app.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return serialize_user(current_user)


@app.get("/dashboard")
async def dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == "hr":
        org_id = current_user.organization_id
        active_jobs = db.query(JobPost).filter(JobPost.organization_id == org_id).count() if org_id else 0
        applications = (
            db.query(JobApplication)
            .join(JobPost)
            .filter(JobPost.organization_id == org_id)
            .count()
            if org_id
            else 0
        )
        return {
            "user": serialize_user(current_user),
            "metrics": {
                "active_jobs": active_jobs,
                "applications": applications,
                "shortlist": 0,
                "average_score": 0,
            },
        }

    candidate = current_user.candidate_profile
    applications = (
        db.query(JobApplication).filter(JobApplication.candidate_profile_id == candidate.id).count()
        if candidate
        else 0
    )
    jobs = db.query(JobPost).filter(JobPost.status == "published").count()
    return {
        "user": serialize_user(current_user),
        "metrics": {
            "profile_completion": 70,
            "matching_jobs": jobs,
            "applications": applications,
            "feedback": 0,
        },
    }


@app.get("/jobs")
async def list_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == "hr":
        jobs = (
            db.query(JobPost)
            .filter(JobPost.organization_id == current_user.organization_id)
            .order_by(JobPost.created_at.desc())
            .all()
        )
        return {"jobs": [serialize_job(job) for job in jobs]}

    candidate = current_user.candidate_profile
    applied_by_job_id = {}
    if candidate:
        applications = (
            db.query(JobApplication)
            .filter(JobApplication.candidate_profile_id == candidate.id)
            .all()
        )
        applied_by_job_id = {application.job_post_id: application for application in applications}

    jobs = db.query(JobPost).filter(JobPost.status == "published").order_by(JobPost.created_at.desc()).all()
    return {"jobs": [serialize_job(job, applied_by_job_id.get(job.id)) for job in jobs]}


@app.post("/jobs")
async def create_job(
    payload: JobCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(current_user, "hr")
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="Ilan olusturmak icin sirket baglantisi gerekli")

    job = JobPost(
        organization_id=current_user.organization_id,
        created_by_user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        location=payload.location,
        seniority=payload.seniority,
        min_experience_years=payload.min_experience_years,
        must_have_skills=payload.must_have_skills,
        nice_to_have_skills=payload.nice_to_have_skills,
        status=payload.status,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"job": serialize_job(job)}


@app.post("/jobs/{job_id}/apply")
async def apply_to_job(
    job_id: str,
    payload: ApplicationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(current_user, "candidate")
    candidate = current_user.candidate_profile
    if not candidate:
        raise HTTPException(status_code=400, detail="Aday profili bulunamadi")

    job = db.get(JobPost, job_id)
    if not job or job.status != "published":
        raise HTTPException(status_code=404, detail="Ilan bulunamadi")

    existing = (
        db.query(JobApplication)
        .filter(
            JobApplication.job_post_id == job.id,
            JobApplication.candidate_profile_id == candidate.id,
        )
        .first()
    )
    if existing:
        return {"application": serialize_application(existing)}

    application = JobApplication(
        job_post_id=job.id,
        candidate_profile_id=candidate.id,
        status="submitted",
        match_score=None,
        match_breakdown={
            "mode": "loose_job_match",
            "note": "Ilan-basvuru uyumluluk skoru matcher servisi baglaninca hesaplanacak.",
        },
        cover_letter=payload.cover_letter,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return {"application": serialize_application(application)}


@app.get("/applications/me")
async def my_applications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(current_user, "candidate")
    candidate = current_user.candidate_profile
    if not candidate:
        return {"applications": []}
    applications = (
        db.query(JobApplication)
        .filter(JobApplication.candidate_profile_id == candidate.id)
        .order_by(JobApplication.created_at.desc())
        .all()
    )
    return {"applications": [serialize_application(application) for application in applications]}

@app.post("/upload-cv")
async def upload_cv(file: UploadFile = File(...)):
    """
    CV dosyası yükle → parse → LLM extraction → RAG doğrulama
    → KG yaz → Entity Resolution → Embedding → R2 yükle
    """
    allowed_extensions = {".pdf", ".docx"}
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Desteklenmeyen dosya türü. Sadece PDF ve DOCX kabul edilir."
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
        temp_path = Path(temp_file.name)
        content = await file.read()
        temp_file.write(content)

    try:
        result = get_pipeline().process(temp_path)

        if result is None:
            raise HTTPException(
                status_code=500,
                detail="CV işlenirken hata oluştu. Lütfen tekrar deneyin."
            )

        # R2'ye yükle
        cv_id = result.get("cv_id")
        if cv_id:
            try:
                object_name = r2_upload(cv_id, temp_path, file.filename)
                with get_neo4j_driver().session() as session:
                    session.run("""
                        MATCH (c:Candidate {id: $id})
                        SET c.cv_object_name = $object_name,
                            c.cv_original_name = $original_name
                    """, id=cv_id, object_name=object_name,
                         original_name=file.filename)
            except Exception as e:
                logger.warning(f"⚠️ R2 yükleme başarısız (pipeline tamamlandı): {e}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail="CV işlenirken hata oluştu. Lütfen tekrar deneyin.")

    finally:
        if temp_path.exists():
            os.unlink(temp_path)

@app.get("/download-cv/{candidate_id}")
async def download_cv(candidate_id: str):
    """Aday CV dosyasını R2'den indirir"""
    with get_neo4j_driver().session() as session:
        record = session.run("""
            MATCH (c:Candidate {id: $id})
            RETURN c.cv_object_name AS object_name,
                   c.cv_original_name AS original_name,
                   c.file_hash AS file_hash
        """, id=candidate_id).single()

    if not record:
        raise HTTPException(status_code=404, detail="CV dosyası bulunamadı")

    if not record["object_name"]:
        local_cv = _find_local_cv_by_hash(record["file_hash"])
        if not local_cv:
            raise HTTPException(status_code=404, detail="CV dosyası bulunamadı")
        return Response(
            content=local_cv.read_bytes(),
            media_type=mimetypes.guess_type(local_cv.name)[0] or "application/octet-stream",
            headers={
                "Content-Disposition":
                    f"attachment; filename=\"{record['original_name'] or local_cv.name}\""
            },
        )

    try:
        file_bytes = r2_download(record["object_name"])
    except Exception as e:
        logger.error(f"R2 download error: {e}")
        raise HTTPException(status_code=404, detail="CV dosyasına erişilemiyor")

    return Response(
        content=file_bytes,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition":
                f"attachment; filename=\"{record['original_name'] or 'cv.docx'}\""
        },
    )


@app.get("/candidates/{candidate_id}")
async def candidate_detail(candidate_id: str):
    """Aday detayını popup/detay ekranı için döner"""
    with get_neo4j_driver().session() as session:
        record = session.run("""
            MATCH (c:Candidate {id: $id})

            OPTIONAL MATCH (c)-[hs:HAS_SKILL]->(s:Skill)
            WITH c, collect({
                name: s.name,
                category: hs.category,
                years: hs.years_experience,
                level: hs.level,
                confidence: hs.confidence
            }) AS raw_skills
            WITH c, [x IN raw_skills WHERE x.name IS NOT NULL] AS skills

            OPTIONAL MATCH (c)-[:HAS_EXPERIENCE]->(e:Experience)-[:AT_COMPANY]->(co:Company)
            WITH c, skills, collect({
                role: e.role_title,
                company: co.name,
                start_date: e.start_date,
                end_date: e.end_date,
                is_current: e.is_current,
                location: e.location,
                description: e.description
            }) AS raw_experiences
            WITH c, skills, [x IN raw_experiences WHERE x.role IS NOT NULL OR x.company IS NOT NULL] AS experiences

            OPTIONAL MATCH (c)-[:HAS_EDUCATION]->(ed:Education)-[:AT_INSTITUTION]->(i:Institution)
            WITH c, skills, experiences, collect({
                degree: ed.degree,
                field: ed.field,
                institution: i.name,
                gpa: ed.gpa
            }) AS raw_educations
            WITH c, skills, experiences, [x IN raw_educations WHERE x.degree IS NOT NULL OR x.institution IS NOT NULL] AS educations

            OPTIONAL MATCH (c)-[:SPEAKS]->(l:Language)
            WITH c, skills, experiences, educations, [x IN collect(l.name) WHERE x IS NOT NULL] AS languages

            OPTIONAL MATCH (c)-[:HAS_CERTIFICATION]->(ct:Certification)
            WITH c, skills, experiences, educations, languages, [x IN collect(ct.name) WHERE x IS NOT NULL] AS certifications

            RETURN
                c.id AS id,
                c.name AS name,
                c.email AS email,
                c.phone AS phone,
                c.location AS location,
                c.summary AS summary,
                c.file_hash AS file_hash,
                c.cv_object_name AS cv_object_name,
                c.cv_original_name AS cv_original_name,
                skills,
                experiences,
                educations,
                languages,
                certifications
        """, id=candidate_id).single()

    if not record:
        raise HTTPException(status_code=404, detail="Aday bulunamadi")

    data = record.data()
    data["cv_available"] = bool(data.get("cv_object_name") or _find_local_cv_by_hash(data.get("file_hash")))
    if data.get("file_hash"):
        data["file_hash_short"] = f"{data['file_hash'][:10]}..."
    return data


@app.post("/search-candidates", response_model=List[Dict])
async def search_candidates(query: QuerySpec):
    """İK sorgusuna göre en uygun adayları getir"""
    try:
        results = get_matcher().search(query, limit=10)
        return results
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/resolve-entities")
async def resolve_entities():
    """KG'deki duplicate düğümleri birleştirir (Entity Resolution)"""
    try:
        from app.extraction.entity_resolver import EntityResolver
        resolver = EntityResolver(get_neo4j_driver())
        stats = resolver.resolve_all()
        return {"status": "success", "merged": stats}
    except Exception as e:
        logger.error(f"ER error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/embed-all")
async def embed_all():
    """Tüm adaylar için embedding üret"""
    try:
        from app.extraction.embedding_service import EmbeddingService
        svc = EmbeddingService(get_neo4j_driver())
        svc.ensure_vector_index()
        count = svc.embed_all_candidates()
        return {"status": "success", "embedded": count}
    except Exception as e:
        logger.error(f"Embed error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    

_nl_parser = None

def get_nl_parser():
    global _nl_parser
    if _nl_parser is None:
        from app.query.nl_parser import NLQueryParser
        _nl_parser = NLQueryParser()
    return _nl_parser

@app.post("/nl-search")
async def nl_search(body: dict):
    """
    Doğal dil sorgusu → QuerySpec → Aday arama
    Body: {"query": "5 yıl Python deneyimi olan senior backend developer"}
    """
    nl_text = body.get("query", "").strip()
    if not nl_text:
        raise HTTPException(status_code=400, detail="query alanı boş olamaz")

    try:
        query_spec = get_nl_parser().parse(nl_text)
        results = get_matcher().search(query_spec, limit=10)
        return {
            "parsed_query": query_spec.model_dump(),
            "results": results,
        }
    except Exception as e:
        logger.error(f"NL search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
