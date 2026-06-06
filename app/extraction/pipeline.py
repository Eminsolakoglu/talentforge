from pathlib import Path
from typing import Optional
import logging
import hashlib

from app.extraction.parser import CVParser
from app.extraction.llm_extractor import LLMExtractor
from app.extraction.kg_loader import KGLoader
from app.core.database import get_neo4j_driver
from app.extraction.entity_resolver import EntityResolver
from app.extraction.embedding_service import EmbeddingService
from app.extraction.rag_validator import RAGValidator

logger = logging.getLogger(__name__)


class CVProcessingPipeline:
    """CV dosyasını parse edip LLM ile yapılandırılmış bilgi çıkaran ve KG'ye yazan uçtan uca pipeline"""

    def __init__(self):
        self.parser = CVParser()
        self.extractor = LLMExtractor()
        self.kg_loader = KGLoader(get_neo4j_driver())
        self.entity_resolver = EntityResolver(get_neo4j_driver())
        self.embedding_service = EmbeddingService(get_neo4j_driver())
        self.embedding_service.ensure_vector_index()
        self.rag_validator = RAGValidator()
        logger.info("✅ CVProcessingPipeline initialized with model.")

    def process(self, file_path: str | Path) -> Optional[dict]:
        """
        CV dosyasını işler ve sonucu dict olarak döner.
        Dict içinde cv_id, candidate_name, skills, experiences vb. alanlar bulunur.
        Hata veya duplicate durumunda None döner.

        Adımlar:
          0. Hash kontrolü (duplicate)
          1. Parse (PDF/DOCX)
          2. LLM Extraction (Few-shot + CoT + Semantic Inference)
          3. RAG Doğrulama (halüsinasyon tespiti)
          4. KG Yazma (Neo4j)
          5. Entity Resolution (duplicate düğüm birleştirme)
          6. Embedding üretme (vektör arama için)
        """
        file_path = Path(file_path)

        try:
            logger.info(f"🚀 Pipeline started for: {file_path.name}")

            # 0. Hash kontrolü — aynı CV tekrar yüklenmesin
            file_hash = self._compute_hash(file_path)
            if self._is_duplicate(file_hash):
                logger.info("⏭️ Bu CV zaten yüklü, atlanıyor")
                return None

            # 1. Parse
            parse_result = self.parser.parse(file_path)
            raw_text = parse_result.get("raw_text", "")

            if not raw_text or len(raw_text) < 50:
                logger.warning("CV metni çok kısa veya boş")
                return None

            # 2. LLM Extraction
            extraction = self.extractor.extract(raw_text)
            if not extraction:
                logger.error("LLM extraction failed")
                return None

            # 3. RAG Doğrulama
            validation = self.rag_validator.validate(extraction, raw_text)
            extraction = validation.cleaned_extraction
            if validation.quarantine_count > 0:
                logger.warning(
                    f"⚠️ {validation.quarantine_count} çıkarım quarantine'e alındı "
                    f"— halüsinasyon oranı: %{validation.hallucination_rate:.1f}"
                )

            # 4. KG'ye yaz
            cv_id = self.kg_loader.save_candidate(extraction, file_hash=file_hash)

            # 5. Entity Resolution — duplicate düğümleri birleştir
            er_stats = self.entity_resolver.resolve_all()
            if sum(er_stats.values()) > 0:
                logger.info(f"🔗 Entity Resolution: {er_stats}")

            # 6. Embedding üret
            self.embedding_service.embed_candidate(cv_id)

            logger.info(f"✅ Pipeline completed successfully for: {file_path.name} (ID: {cv_id})")

            # cv_id'yi de içeren dict döndür
            result = extraction.model_dump()
            result["cv_id"] = cv_id
            return result

        except Exception as e:
            logger.error(f"❌ Pipeline error: {e}")
            return None

    def extract_only(self, file_path: str | Path) -> Optional[dict]:
        """CV'yi parse + LLM + RAG ile çıkarır, Neo4j/R2 kaydı yapmaz."""
        file_path = Path(file_path)
        try:
            logger.info(f"Preview extraction started for: {file_path.name}")
            file_hash = self._compute_hash(file_path)
            parse_result = self.parser.parse(file_path)
            raw_text = parse_result.get("raw_text", "")
            if not raw_text or len(raw_text) < 50:
                logger.warning("CV metni çok kısa veya boş")
                return None

            extraction = self.extractor.extract(raw_text)
            if not extraction:
                logger.error("LLM extraction failed")
                return None

            validation = self.rag_validator.validate(extraction, raw_text)
            extraction = validation.cleaned_extraction
            result = extraction.model_dump()
            result["file_hash"] = file_hash
            result["preview_only"] = True
            return result
        except Exception as e:
            logger.error(f"Preview extraction error: {e}")
            return None

    def commit_extraction(self, extraction, file_hash: str | None = None) -> Optional[str]:
        """Önizlenen extraction sonucunu Neo4j'ye yazar ve embedding üretir."""
        try:
            if self._is_duplicate(file_hash):
                logger.info("Bu CV zaten yüklü, kayıt atlandı")
                return None
            cv_id = self.kg_loader.save_candidate(extraction, file_hash=file_hash)
            er_stats = self.entity_resolver.resolve_all()
            if sum(er_stats.values()) > 0:
                logger.info(f"Entity Resolution: {er_stats}")
            self.embedding_service.embed_candidate(cv_id)
            return cv_id
        except Exception as e:
            logger.error(f"Commit extraction error: {e}")
            return None

    def _compute_hash(self, file_path: Path) -> str:
        """Dosya içeriğinden SHA256 hash üretir"""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _is_duplicate(self, file_hash: str) -> bool:
        """Aynı hash'li CV daha önce yüklendi mi kontrol eder"""
        with self.kg_loader.driver.session() as session:
            result = session.run(
                "MATCH (c:Candidate {file_hash: $hash}) RETURN c.name AS name",
                hash=file_hash,
            )
            record = result.single()
            if record:
                logger.info(f"⏭️ Duplicate CV: {record['name']}")
                return True
        return False
