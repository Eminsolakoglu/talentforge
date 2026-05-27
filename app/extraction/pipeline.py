from pathlib import Path
from typing import Optional
import logging
import uuid

from app.extraction.parser import CVParser
from app.extraction.llm_extractor import LLMExtractor
from app.extraction.kg_loader import KGLoader
from app.schemas.cv_extraction import CVExtraction
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
        logger.info(f"✅ CVProcessingPipeline initialized with model.")

    def process(self, file_path: str | Path) -> Optional[CVExtraction]:
        """
        CV dosyasını işler:
        1. Parse eder
        2. LLM ile yapılandırılmış bilgi çıkarır
        3. Neo4j KG'ye yazar
        """
        file_path = Path(file_path)
        
        try:
            logger.info(f"🚀 Pipeline started for: {file_path.name}")

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
            
            # 3. RAG Doğrulama  ← BURAYA EKLE
            validation = self.rag_validator.validate(extraction, raw_text)
            extraction = validation.cleaned_extraction
            if validation.quarantine_count > 0:
                logger.warning(f"⚠️ {validation.quarantine_count} çıkarım quarantine'e alındı — halüsinasyon oranı: %{validation.hallucination_rate:.1f}")

            # 3. KG'ye yaz
            cv_id = self.kg_loader.save_candidate(extraction)

            # 4. Entity Resolution — duplicate düğümleri birleştir
            er_stats = self.entity_resolver.resolve_all()
            if sum(er_stats.values()) > 0:
                logger.info(f"🔗 Entity Resolution: {er_stats}")

            # 5. Embedding üret
            self.embedding_service.embed_candidate(cv_id)

            logger.info(f"✅ Pipeline completed successfully for: {file_path.name} (ID: {cv_id})")
            return extraction

        except Exception as e:
            logger.error(f"❌ Pipeline error: {e}")
            return None