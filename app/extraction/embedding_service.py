"""
Embedding Servisi — Aday profil özetlerinden embedding üretir.

Model: paraphrase-multilingual-MiniLM-L12-v2 (384 boyut, Türkçe+İngilizce)
Öncelik: HuggingFace Inference API (RAM kullanmaz) → Lokal model (fallback)
"""

import os
import logging
import math
from typing import List, Optional

import requests as http_requests
from neo4j import Driver

logger = logging.getLogger(__name__)

# ── Sabitler ──────────────────────────────────────────────────────────

_HF_MODEL = os.getenv(
    "HF_EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
_DIMENSIONS = 384
_local_model = None


# ── Embedding üretimi ─────────────────────────────────────────────────

def get_dimensions() -> int:
    return _DIMENSIONS


def generate_embedding(text: str) -> List[float]:
    """Embedding üretir.

    EMBEDDING_BACKEND=huggingface/hf ise sadece HF API kullanır.
    EMBEDDING_BACKEND=local ise sadece lokal model kullanır.
    Varsayılan auto modunda HF başarısız olursa lokal fallback yapar.
    """
    backend = os.getenv("EMBEDDING_BACKEND", "auto").lower().strip()
    hf_token = os.getenv("HF_TOKEN")

    if backend in {"local", "sentence-transformers"}:
        return _embed_local(text)

    if backend in {"huggingface", "hf"} and not hf_token:
        raise ValueError("EMBEDDING_BACKEND=huggingface secildi ama HF_TOKEN bulunamadi")

    if hf_token:
        try:
            return _embed_via_api(text, hf_token)
        except Exception as e:
            if backend in {"huggingface", "hf"}:
                raise
            logger.warning(f"⚠️ HF API embedding başarısız, lokal deneniyor: {e}")

    return _embed_local(text)


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """Birden fazla metin için toplu embedding üretir"""
    return [generate_embedding(t) for t in texts]


def _embed_via_api(text: str, token: str) -> List[float]:
    """HuggingFace Router / HF Inference ile embedding (RAM kullanmaz)"""
    response = http_requests.post(
        f"https://router.huggingface.co/hf-inference/models/{_HF_MODEL}/pipeline/feature-extraction",
        headers={"Authorization": f"Bearer {token}"},
        json={"inputs": text, "options": {"wait_for_model": True}},
        timeout=30,
    )
    response.raise_for_status()
    return _normalize_embedding(_coerce_embedding(response.json()))


def _coerce_embedding(payload) -> List[float]:
    """HF feature-extraction yanıtını tek 384 boyutlu vektöre indirger."""
    if isinstance(payload, dict) and "error" in payload:
        raise RuntimeError(payload["error"])

    if not isinstance(payload, list) or not payload:
        raise RuntimeError("HF embedding yaniti beklenen formatta degil")

    if all(isinstance(x, (int, float)) for x in payload):
        return [float(x) for x in payload]

    if all(isinstance(row, list) for row in payload):
        rows = payload
        if rows and rows[0] and isinstance(rows[0][0], list):
            rows = rows[0]
        if not rows:
            raise RuntimeError("HF embedding yaniti bos")
        dims = len(rows[0])
        return [
            sum(float(row[i]) for row in rows if len(row) == dims) / len(rows)
            for i in range(dims)
        ]

    raise RuntimeError("HF embedding yaniti beklenen formatta degil")


def _normalize_embedding(vector: List[float]) -> List[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return vector
    return [value / norm for value in vector]


def _embed_local(text: str) -> List[float]:
    """Lokal sentence-transformers ile embedding (fallback)"""
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"📦 Lokal embedding modeli yükleniyor: {_HF_MODEL}...")
        _local_model = SentenceTransformer(_HF_MODEL)
        logger.info("✅ Lokal embedding modeli hazır")
    return _local_model.encode(text, normalize_embeddings=True).tolist()


# ── Aday profil özeti ─────────────────────────────────────────────────

def build_candidate_summary(candidate_data: dict) -> str:
    """
    KG'den çekilen aday verisinden embedding için özet metin üretir.
    Ham CV yerine yapılandırılmış veriden üretmek gürültüyü azaltır.
    """
    parts = []

    if candidate_data.get("summary"):
        parts.append(candidate_data["summary"])

    # Yetenekler
    skills = candidate_data.get("skills", [])
    if skills:
        skill_strs = []
        for s in skills:
            name = s.get("name", "")
            years = s.get("years")
            skill_strs.append(f"{name} ({years}y)" if years else name)
        parts.append("Skills: " + ", ".join(skill_strs))

    # Deneyimler
    experiences = candidate_data.get("experiences", [])
    if experiences:
        exp_strs = []
        for exp in experiences:
            role = exp.get("role", "")
            company = exp.get("company", "")
            if role and company:
                exp_strs.append(f"{role} at {company}")
        if exp_strs:
            parts.append("Experience: " + "; ".join(exp_strs))

    # Eğitim
    educations = candidate_data.get("educations", [])
    if educations:
        edu_strs = []
        for edu in educations:
            degree = edu.get("degree", "")
            field = edu.get("field", "")
            institution = edu.get("institution", "")
            if degree and institution:
                edu_strs.append(f"{degree} {field} at {institution}")
        if edu_strs:
            parts.append("Education: " + "; ".join(edu_strs))

    projects = candidate_data.get("projects", [])
    if projects:
        project_strs = []
        for project in projects:
            name = project.get("name", "")
            description = project.get("description", "")
            if name:
                project_strs.append(f"{name}: {description}" if description else name)
        if project_strs:
            parts.append("Projects: " + "; ".join(project_strs))

    # Lokasyon
    if candidate_data.get("location"):
        parts.append(f"Location: {candidate_data['location']}")

    return ". ".join(parts)


# ── Ana servis sınıfı ─────────────────────────────────────────────────

class EmbeddingService:
    """Neo4j'deki adaylar için embedding üretip vektör indeksine yazar"""

    def __init__(self, driver: Driver):
        self.driver = driver

    def ensure_vector_index(self):
        """Neo4j'de vektör indeksini oluşturur (yoksa)"""
        with self.driver.session() as session:
            try:
                session.run(f"""
                    CREATE VECTOR INDEX candidate_embedding IF NOT EXISTS
                    FOR (c:Candidate) ON (c.embedding)
                    OPTIONS {{
                        indexConfig: {{
                            `vector.dimensions`: {_DIMENSIONS},
                            `vector.similarity_function`: 'cosine'
                        }}
                    }}
                """)
                logger.info(f"✅ Vector index hazır ({_DIMENSIONS} boyut, cosine)")
            except Exception as e:
                logger.warning(f"⚠️ Vector index: {e}")

    def embed_candidate(self, candidate_id: str):
        """Tek bir adayın embedding'ini üretip Neo4j'e yazar"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Candidate {id: $id})

                OPTIONAL MATCH (c)-[hs:HAS_SKILL]->(s:Skill)
                WITH c, collect({name: s.name, years: hs.years_experience}) AS skills

                OPTIONAL MATCH (c)-[:HAS_EXPERIENCE]->(e:Experience)-[:AT_COMPANY]->(co:Company)
                WITH c, skills, collect({role: e.role_title, company: co.name}) AS experiences

                OPTIONAL MATCH (c)-[:HAS_EDUCATION]->(ed:Education)-[:AT_INSTITUTION]->(i:Institution)
                WITH c, skills, experiences, collect({
                    degree: ed.degree, field: ed.field, institution: i.name
                }) AS educations

                OPTIONAL MATCH (c)-[:HAS_PROJECT]->(p:Project)
                WITH c, skills, experiences, educations, collect({
                    name: p.name, description: p.description, role: p.role
                }) AS projects

                RETURN c.name AS name, c.summary AS summary, c.location AS location,
                       skills, experiences, educations, projects
            """, id=candidate_id)

            record = result.single()
            if not record:
                logger.warning(f"⚠️ Aday bulunamadı: {candidate_id}")
                return

            candidate_data = record.data()
            summary_text = build_candidate_summary(candidate_data)
            embedding = generate_embedding(summary_text)

            session.run("""
                MATCH (c:Candidate {id: $id})
                SET c.embedding = $embedding,
                    c.embedding_text = $summary_text
            """, id=candidate_id, embedding=embedding, summary_text=summary_text)

            logger.info(f"✅ Embedding üretildi: {candidate_data.get('name')} ({len(embedding)} boyut)")

    def embed_all_candidates(self) -> int:
        """Embedding'i olmayan tüm adaylar için embedding üretir"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Candidate)
                WHERE c.embedding IS NULL
                RETURN c.id AS id, c.name AS name
            """)
            candidates = [r.data() for r in result]

        if not candidates:
            logger.info("ℹ️ Tüm adayların embedding'i zaten var")
            return 0

        for cand in candidates:
            self.embed_candidate(cand["id"])

        logger.info(f"✅ {len(candidates)} aday için embedding üretildi")
        return len(candidates)

    def vector_search(self, query_text: str, top_k: int = 20) -> List[dict]:
        """Sorgu metnine en yakın adayları vektör benzerliği ile bulur"""
        query_embedding = generate_embedding(query_text)

        with self.driver.session() as session:
            result = session.run("""
                CALL db.index.vector.queryNodes(
                    'candidate_embedding', $top_k, $embedding
                ) YIELD node, score
                RETURN node.id AS id, node.name AS name, score
                ORDER BY score DESC
            """, top_k=top_k, embedding=query_embedding)

            return [r.data() for r in result]
