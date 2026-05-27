"""
RAG Doğrulama Döngüsü — Halüsinasyon Tespiti

H4 hipotezi: KG-destekli doğrulama, halüsinasyon oranını %20+ azaltır.

İki doğrulama katmanı:
  1. Kanıt Tabanlı (Evidence): evidence_text orijinal CV'de var mı?
  2. KG Tutarlılık: Tarih çelişkisi, overlapping deneyim var mı?

Şüpheli çıkarımlar quarantine listesine alınır — KG'ye yazılmaz.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from app.schemas.cv_extraction import CVExtraction

logger = logging.getLogger(__name__)

# ── Eşikler ──────────────────────────────────────────────────────────

EVIDENCE_WORD_THRESHOLD = 0.60   # evidence_text kelimelerinin %60'ı CV'de olmalı
CONFIDENCE_MIN_THRESHOLD = 0.60  # Bu altı direkt quarantine
FUZZY_MATCH_THRESHOLD = 0.50     # Warning ile quarantine arasındaki sınır


# ── Veri yapıları ─────────────────────────────────────────────────────

@dataclass
class ValidationIssue:
    field: str
    value: str
    reason: str
    severity: str   # "quarantine" | "warning"
    confidence: float


@dataclass
class ValidationResult:
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    quarantine_count: int = 0
    warning_count: int = 0
    hallucination_rate: float = 0.0
    cleaned_extraction: Optional[CVExtraction] = None

    def summary(self) -> str:
        return (
            f"{self.quarantine_count} quarantine, "
            f"{self.warning_count} uyarı, "
            f"halüsinasyon: %{self.hallucination_rate:.1f}"
        )


# ── Ana sınıf ─────────────────────────────────────────────────────────

class RAGValidator:
    """
    LLM çıkarımını orijinal CV metniyle çapraz doğrular.

    Kullanım:
        validator = RAGValidator()
        result = validator.validate(extraction, cv_text)
        kg_loader.save(result.cleaned_extraction)
    """

    def validate(self, extraction: CVExtraction, cv_text: str) -> ValidationResult:
        """Ana doğrulama — extraction + orijinal CV metni alır, temizlenmiş extraction döner"""
        issues = []
        total_checks = len(extraction.skills) + len(extraction.experiences)

        # 1. Confidence filtresi
        conf_issues = self._check_confidence(extraction)
        issues.extend(conf_issues)

        # 2. Deneyim kanıt kontrolü
        exp_issues = self._validate_experiences(extraction, cv_text)
        issues.extend(exp_issues)

        # 3. Skill kanıt kontrolü
        skill_issues = self._validate_skills(extraction, cv_text)
        issues.extend(skill_issues)

        # 4. Tarih tutarlılığı
        date_issues = self._check_date_consistency(extraction)
        issues.extend(date_issues)

        # 5. Overlapping deneyim
        overlap_issues = self._check_overlapping_experiences(extraction)
        issues.extend(overlap_issues)

        quarantine_count = sum(1 for i in issues if i.severity == "quarantine")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        hallucination_rate = (quarantine_count / total_checks * 100) if total_checks > 0 else 0.0

        result = ValidationResult(
            is_valid=quarantine_count == 0,
            issues=issues,
            quarantine_count=quarantine_count,
            warning_count=warning_count,
            hallucination_rate=hallucination_rate,
            cleaned_extraction=extraction,
        )

        # Loglama
        if quarantine_count > 0:
            logger.warning(f"⚠️ RAG Validator: {result.summary()}")
        else:
            logger.info(f"✅ RAG Validator: {result.summary()}")

        for issue in issues:
            icon = "🚫" if issue.severity == "quarantine" else "⚠️"
            logger.info(f"  {icon} [{issue.field}] {issue.value[:60]} — {issue.reason}")

        return result

    # ── Doğrulama katmanları ──────────────────────────────────────────

    def _check_confidence(self, extraction: CVExtraction) -> List[ValidationIssue]:
        """Düşük confidence'lı skill'leri kaldır"""
        issues = []
        valid_skills = []

        for skill in extraction.skills:
            if skill.confidence < CONFIDENCE_MIN_THRESHOLD:
                issues.append(ValidationIssue(
                    field="skill.confidence",
                    value=skill.name,
                    reason=f"Confidence çok düşük ({skill.confidence:.2f} < {CONFIDENCE_MIN_THRESHOLD})",
                    severity="quarantine",
                    confidence=skill.confidence,
                ))
            else:
                valid_skills.append(skill)

        extraction.skills = valid_skills
        return issues

    def _validate_experiences(self, extraction: CVExtraction, cv_text: str) -> List[ValidationIssue]:
        """Deneyim evidence_text'ini CV metniyle doğrula"""
        issues = []
        valid_exps = []

        for exp in extraction.experiences:
            evidence = exp.evidence_text or ""

            if not evidence:
                valid_exps.append(exp)
                continue

            overlap = self._word_overlap(evidence, cv_text)

            if overlap < FUZZY_MATCH_THRESHOLD:
                issues.append(ValidationIssue(
                    field="experience.evidence",
                    value=f"{exp.company_name} — {exp.role_title}",
                    reason=f"Kanıt metni CV'de bulunamadı (örtüşme: {overlap:.0%})",
                    severity="quarantine",
                    confidence=exp.confidence,
                ))
                continue  # quarantine — listeye ekleme
            elif overlap < EVIDENCE_WORD_THRESHOLD:
                issues.append(ValidationIssue(
                    field="experience.evidence",
                    value=f"{exp.company_name} — {exp.role_title}",
                    reason=f"Kanıt metni zayıf (örtüşme: {overlap:.0%})",
                    severity="warning",
                    confidence=exp.confidence,
                ))

            valid_exps.append(exp)

        extraction.experiences = valid_exps
        return issues

    def _validate_skills(self, extraction: CVExtraction, cv_text: str) -> List[ValidationIssue]:
        """Skill evidence_text'ini CV metniyle doğrula"""
        issues = []
        valid_skills = []

        for skill in extraction.skills:
            evidence = skill.evidence_text or ""

            # evidence yoksa skill adının geçip geçmediğine bak
            if not evidence:
                if not self._contains(cv_text, skill.name):
                    issues.append(ValidationIssue(
                        field="skill.evidence",
                        value=skill.name,
                        reason="Skill CV'de geçmiyor ve evidence_text yok",
                        severity="warning",
                        confidence=skill.confidence,
                    ))
                valid_skills.append(skill)
                continue

            overlap = self._word_overlap(evidence, cv_text)

            if overlap < FUZZY_MATCH_THRESHOLD:
                issues.append(ValidationIssue(
                    field="skill.evidence",
                    value=skill.name,
                    reason=f"Kanıt metni CV'de bulunamadı (örtüşme: {overlap:.0%})",
                    severity="quarantine",
                    confidence=skill.confidence,
                ))
                continue
            elif overlap < EVIDENCE_WORD_THRESHOLD:
                issues.append(ValidationIssue(
                    field="skill.evidence",
                    value=skill.name,
                    reason=f"Kanıt metni zayıf (örtüşme: {overlap:.0%})",
                    severity="warning",
                    confidence=skill.confidence,
                ))

            valid_skills.append(skill)

        extraction.skills = valid_skills
        return issues

    def _check_date_consistency(self, extraction: CVExtraction) -> List[ValidationIssue]:
        """Tarih mantık hatalarını tespit eder"""
        issues = []

        for exp in extraction.experiences:
            start = self._parse_date(exp.start_date)
            end = self._parse_date(exp.end_date)

            if start and end and end < start:
                issues.append(ValidationIssue(
                    field="experience.dates",
                    value=f"{exp.company_name}: {exp.start_date} → {exp.end_date}",
                    reason="Bitiş tarihi başlangıç tarihinden önce",
                    severity="warning",
                    confidence=exp.confidence,
                ))

            if start and start > 2026 * 12 + 5:
                issues.append(ValidationIssue(
                    field="experience.start_date",
                    value=f"{exp.company_name}: {exp.start_date}",
                    reason="Başlangıç tarihi gelecekte",
                    severity="warning",
                    confidence=exp.confidence,
                ))

        return issues

    def _check_overlapping_experiences(self, extraction: CVExtraction) -> List[ValidationIssue]:
        """Çakışan tam zamanlı deneyimleri tespit eder"""
        issues = []
        dated = []

        for exp in extraction.experiences:
            start = self._parse_date(exp.start_date)
            end = self._parse_date(exp.end_date) or (2026 * 12 + 5)
            if start:
                dated.append((exp, start, end))

        for i, (exp1, s1, e1) in enumerate(dated):
            for exp2, s2, e2 in dated[i + 1:]:
                is_intern = any(
                    kw in (r or "").lower()
                    for r in [exp1.role_title, exp2.role_title]
                    for kw in ["staj", "intern"]
                )
                if is_intern:
                    continue

                overlap = min(e1, e2) - max(s1, s2)
                if overlap > 6:
                    issues.append(ValidationIssue(
                        field="experience.overlap",
                        value=f"{exp1.company_name} ↔ {exp2.company_name}",
                        reason=f"{overlap} ay çakışıyor",
                        severity="warning",
                        confidence=min(exp1.confidence, exp2.confidence),
                    ))

        return issues

    # ── Yardımcı metodlar ─────────────────────────────────────────────

    def _contains(self, text: str, query: str) -> bool:
        if not text or not query:
            return False
        return query.lower().strip() in text.lower()

    def _word_overlap(self, text1: str, text2: str) -> float:
        """text1'deki anlamlı kelimelerin text2'de geçme oranı"""
        if not text1 or not text2:
            return 0.0
        words1 = set(re.findall(r'\b\w{3,}\b', text1.lower()))
        words2 = set(re.findall(r'\b\w{3,}\b', text2.lower()))
        if not words1:
            return 0.0
        return len(words1 & words2) / len(words1)

    def _parse_date(self, date_str: Optional[str]) -> Optional[int]:
        """'Şub 2022' → yıl*12+ay"""
        if not date_str:
            return None
        month_map = {
            "oca": 1, "sub": 2, "mar": 3, "nis": 4, "may": 5, "haz": 6,
            "tem": 7, "agu": 8, "eyl": 9, "eki": 10, "kas": 11, "ara": 12,
            "jan": 1, "feb": 2, "apr": 4, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        normalized = ""
        for ch in date_str.lower():
            normalized += {"ş": "s", "ğ": "g", "ü": "u", "ö": "o",
                           "ç": "c", "ı": "i"}.get(ch, ch)
        parts = normalized.split()
        if len(parts) == 2:
            month = month_map.get(parts[0][:3], 0)
            try:
                return int(parts[1]) * 12 + month
            except ValueError:
                return None
        return None