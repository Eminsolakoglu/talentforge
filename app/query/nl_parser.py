"""
Doğal Dil → QuerySpec Dönüştürücü

İK uzmanının yazdığı serbest metni yapısal QuerySpec'e çevirir.
Aynı LLM backend'i kullanır (HF/Groq).

Örnek:
  "5 yıl Python deneyimi olan İstanbul'da yaşayan senior backend developer"
  →
  {
    "title": "Backend Developer",
    "seniority": "senior",
    "must_have_skills": ["Python"],
    "min_experience_years": 5,
    "locations": ["Istanbul"]
  }
"""

import logging
import os
import instructor
from openai import OpenAI
from dotenv import load_dotenv
from app.schemas.query import QuerySpec

load_dotenv()
logger = logging.getLogger(__name__)

NL_SYSTEM_PROMPT = """\
Sen bir İK (İnsan Kaynakları) uzmanısın. Verilen iş ilanı veya arama metnini
yapısal bir arama kriterine dönüştür.

KURALLAR:
- must_have_skills: Metinde açıkça zorunlu belirtilen yetenekler
- nice_to_have_skills: "tercih edilir", "artı", "bonus" gibi ifadeler
- seniority: junior | mid | senior | lead (metinden çıkar, yoksa null)
- min_experience_years: Sayısal değer, "5+ yıl" → 5, yoksa 0
- locations: Şehir isimleri, "uzaktan/remote" → ["Remote"]
- education_level: bsc | msc | phd (yoksa null)
- languages: Dil gereksinimleri varsa ekle
- free_text: Yapısal alanlara sığmayan geri kalan metin

ÖNEMLİ:
- Metinde olmayan bilgiyi uydurma
- Skill isimlerini normalize et (JS→JavaScript, K8s→Kubernetes)
- Türkçe veya İngilizce giriş olabilir

ÖRNEKLER:

Giriş: "İstanbul'da 5+ yıl Python ve AWS deneyimi olan senior backend mühendisi arıyoruz.
Docker ve Kubernetes bilmesi tercih edilir. Yüksek lisans tercihen."
Çıktı:
{
  "title": "Backend Engineer",
  "seniority": "senior",
  "must_have_skills": ["Python", "AWS"],
  "nice_to_have_skills": ["Docker", "Kubernetes"],
  "min_experience_years": 5,
  "locations": ["Istanbul"],
  "education_level": "msc",
  "languages": [],
  "must_have_certifications": [],
  "preferred_industries": [],
  "free_text": null
}

Giriş: "Fintech sektöründe deneyimli, React ve Node.js bilen full stack developer.
Agile metodoloji şart. İngilizce B2 seviye gerekli. Remote çalışma mümkün."
Çıktı:
{
  "title": "Full Stack Developer",
  "seniority": null,
  "must_have_skills": ["React", "Node.js", "Agile"],
  "nice_to_have_skills": [],
  "min_experience_years": 0,
  "locations": ["Remote"],
  "education_level": null,
  "languages": [{"code": "English", "min_level": "B2"}],
  "must_have_certifications": [],
  "preferred_industries": ["Fintech"],
  "free_text": null
}
"""


def _build_client():
    groq_key = os.getenv("GROQ_API_KEY")
    hf_token = os.getenv("HF_TOKEN")

    if groq_key:
        return instructor.from_openai(
            OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key),
        ), os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

    elif hf_token:
        return instructor.from_openai(
            OpenAI(base_url="https://router.huggingface.co/v1", api_key=hf_token),
            mode=instructor.Mode.JSON,
        ), os.getenv("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")

    raise ValueError("LLM backend bulunamadı")


class NLQueryParser:
    """Doğal dil sorgusunu QuerySpec'e çevirir"""

    def __init__(self):
        self.client, self.model = _build_client()
        logger.info(f"✅ NLQueryParser hazır — model: {self.model}")

    def parse(self, nl_text: str) -> QuerySpec:
        """
        Serbest metin → QuerySpec

        Args:
            nl_text: İK uzmanının yazdığı doğal dil sorgusu

        Returns:
            QuerySpec Pydantic modeli
        """
        logger.info(f"🔍 NL→QuerySpec dönüşümü: '{nl_text[:80]}...'")

        try:
            query_spec = self.client.chat.completions.create(
                model=self.model,
                response_model=QuerySpec,
                messages=[
                    {"role": "system", "content": NL_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Şu metni QuerySpec'e çevir:\n\n{nl_text}"},
                ],
                temperature=0,
                max_tokens=1024,
                max_retries=2,
            )
            logger.info(
                f"✅ QuerySpec oluşturuldu — "
                f"skills: {query_spec.must_have_skills}, "
                f"seniority: {query_spec.seniority}, "
                f"location: {query_spec.locations}"
            )
            return query_spec

        except Exception as e:
            logger.error(f"❌ NL parse hatası: {e}")
            # Hata durumunda sadece free_text içeren minimal QuerySpec döndür
            return QuerySpec(
                must_have_skills=[],
                nice_to_have_skills=[],
                locations=[],
                languages=[],
                must_have_certifications=[],
                preferred_industries=[],
                free_text=nl_text,
            )