"""
TalentForge Değerlendirme Framework'ü

H1: NER F1 ≥ 0.85, RE F1 ≥ 0.75
H2: Duplicate düğüm oranı ≤ %5
H3: Hibrit sorgu NDCG@10 ≥ 0.70 (baseline'dan %15 iyileşme)
H4: Halüsinasyon azaltma ≥ %20
H5: Precision@5 ≥ 0.70

Kullanım:
    python -m evaluation.evaluator --mode all
    python -m evaluation.evaluator --mode ner
    python -m evaluation.evaluator --mode ablation
"""

import json
import logging
import math
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, asdict

# Proje kök dizinine path ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_neo4j_driver

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


# ── Veri yapıları ─────────────────────────────────────────────────────

@dataclass
class NERResult:
    """NER değerlendirme sonucu"""
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int

    def __str__(self):
        return (
            f"P={self.precision:.3f} R={self.recall:.3f} F1={self.f1:.3f} "
            f"(TP={self.true_positives} FP={self.false_positives} FN={self.false_negatives})"
        )


@dataclass
class MatchingResult:
    """Eşleştirme değerlendirme sonucu"""
    precision_at_5: float
    precision_at_10: float
    ndcg_at_5: float
    ndcg_at_10: float
    mrr: float

    def __str__(self):
        return (
            f"P@5={self.precision_at_5:.3f} P@10={self.precision_at_10:.3f} "
            f"NDCG@5={self.ndcg_at_5:.3f} NDCG@10={self.ndcg_at_10:.3f} "
            f"MRR={self.mrr:.3f}"
        )


@dataclass
class AblationRow:
    """Ablation study tek satırı"""
    config: str
    description: str
    ner_f1: float
    re_f1: float
    hallucination_rate: float
    ndcg_10: float
    precision_5: float
    duplicate_rate: float


# ── Ana değerlendirici ────────────────────────────────────────────────

class Evaluator:
    """Tüm hipotezler için metrik hesaplama"""

    def __init__(self, gold_standard_path: str = "evaluation/gold_standard.json"):
        self.gold_path = Path(gold_standard_path)
        self.gold_data = self._load_gold()
        self.driver = get_neo4j_driver()

    def _load_gold(self) -> List[Dict]:
        if not self.gold_path.exists():
            logger.warning(f"⚠️ Gold standard bulunamadı: {self.gold_path}")
            return []

        with open(self.gold_path, encoding="utf-8") as f:
            return json.load(f)

    # ── H1: NER / RE değerlendirmesi ──────────────────────────────────

    def evaluate_ner(
        self,
        predictions: List[Dict],
        gold_items: List[Dict],
        entity_type: str
    ) -> NERResult:
        """
        Tek bir entity tipi için NER F1 hesaplar.
        entity_type: "skills" | "companies" | "educations" | "experiences"
        """
        tp = fp = fn = 0

        for gold, pred in zip(gold_items, predictions):
            gold_set = self._extract_entity_set(gold, entity_type)
            pred_set = self._extract_entity_set(pred, entity_type)

            tp += len(gold_set & pred_set)
            fp += len(pred_set - gold_set)
            fn += len(gold_set - pred_set)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        return NERResult(precision, recall, f1, tp, fp, fn)

    def evaluate_all_ner(
        self,
        predictions: List[Dict],
        gold_items: List[Dict] = None
    ) -> Dict[str, NERResult]:
        """Tüm entity tipleri için NER değerlendirmesi"""

        # gold_items verilmediyse kendi gold_data'sını kullan
        if gold_items is None:
            gold_items = self.gold_data

        if not gold_items:
            logger.warning("Gold standard yok, NER değerlendirmesi atlanıyor")
            return {}

        # Eşit uzunlukta olduğundan emin ol
        n = min(len(predictions), len(gold_items))
        predictions = predictions[:n]
        gold_items = gold_items[:n]

        results = {}

        for entity_type in ["skills", "companies", "educations"]:
            results[entity_type] = self.evaluate_ner(predictions, gold_items, entity_type)

        # Genel F1 (ağırlıklı ortalama)
        total_tp = sum(r.true_positives for r in results.values())
        total_fp = sum(r.false_positives for r in results.values())
        total_fn = sum(r.false_negatives for r in results.values())

        overall_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
        overall_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
        overall_f1 = (
            2 * overall_p * overall_r / (overall_p + overall_r)
            if (overall_p + overall_r) > 0
            else 0
        )

        results["overall"] = NERResult(
            overall_p,
            overall_r,
            overall_f1,
            total_tp,
            total_fp,
            total_fn
        )

        return results

    def _extract_entity_set(self, record: Dict, entity_type: str) -> set:
        """Bir kayıttan entity setini çıkarır"""
        normalize = lambda x: x.lower().strip() if x else ""

        if entity_type == "skills":
            return {
                normalize(s.get("name", s) if isinstance(s, dict) else s)
                for s in record.get("skills", [])
            }

        elif entity_type == "companies":
            return {
                normalize(e.get("company_name", ""))
                for e in record.get("experiences", [])
            }

        elif entity_type == "educations":
            return {
                normalize(e.get("institution", ""))
                for e in record.get("educations", [])
            }

        return set()

    # ── H2: Duplicate düğüm oranı ─────────────────────────────────────

    def evaluate_duplicate_rate(self) -> Dict[str, float]:
        """KG'deki duplicate düğüm oranını hesaplar"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (s1:Skill), (s2:Skill)
                WHERE id(s1) < id(s2)
                AND toLower(s1.name) = toLower(s2.name)
                RETURN count(*) AS exact_duplicates
            """)
            exact_dups = result.single()["exact_duplicates"]

            total = session.run(
                "MATCH (s:Skill) RETURN count(s) AS cnt"
            ).single()["cnt"]

            total_co = session.run(
                "MATCH (c:Company) RETURN count(c) AS cnt"
            ).single()["cnt"]

            co_dups = session.run("""
                MATCH (c1:Company), (c2:Company)
                WHERE id(c1) < id(c2)
                AND toLower(c1.name) = toLower(c2.name)
                RETURN count(*) AS cnt
            """).single()["cnt"]

        skill_dup_rate = exact_dups / total if total > 0 else 0
        co_dup_rate = co_dups / total_co if total_co > 0 else 0

        return {
            "skill_total": total,
            "skill_duplicates": exact_dups,
            "skill_duplicate_rate": round(skill_dup_rate * 100, 2),
            "company_total": total_co,
            "company_duplicates": co_dups,
            "company_duplicate_rate": round(co_dup_rate * 100, 2),
            "h2_passed": skill_dup_rate * 100 < 5.0,
        }

    # ── H3/H5: Eşleştirme metrikleri ──────────────────────────────────

    def evaluate_matching(
        self,
        query_results: List[List[str]],
        gold_relevant: List[List[str]]
    ) -> MatchingResult:
        """
        Sıralama metriklerini hesaplar.

        query_results: Her sorgu için sistem sıralaması [[aday1, aday2, ...], ...]
        gold_relevant: Her sorgu için ilgili adaylar [[ilgili1, ilgili2], ...]
        """
        p5_scores = []
        p10_scores = []
        ndcg5_scores = []
        ndcg10_scores = []
        rr_scores = []

        for ranked, relevant in zip(query_results, gold_relevant):
            relevant_set = {r.lower() for r in relevant}

            p5 = sum(
                1 for c in ranked[:5]
                if c.lower() in relevant_set
            ) / min(5, len(ranked)) if ranked else 0

            p10 = sum(
                1 for c in ranked[:10]
                if c.lower() in relevant_set
            ) / min(10, len(ranked)) if ranked else 0

            ndcg5 = self._ndcg(ranked[:5], relevant_set)
            ndcg10 = self._ndcg(ranked[:10], relevant_set)

            rr = 0.0
            for i, c in enumerate(ranked, 1):
                if c.lower() in relevant_set:
                    rr = 1.0 / i
                    break

            p5_scores.append(p5)
            p10_scores.append(p10)
            ndcg5_scores.append(ndcg5)
            ndcg10_scores.append(ndcg10)
            rr_scores.append(rr)

        return MatchingResult(
            precision_at_5=sum(p5_scores) / len(p5_scores) if p5_scores else 0,
            precision_at_10=sum(p10_scores) / len(p10_scores) if p10_scores else 0,
            ndcg_at_5=sum(ndcg5_scores) / len(ndcg5_scores) if ndcg5_scores else 0,
            ndcg_at_10=sum(ndcg10_scores) / len(ndcg10_scores) if ndcg10_scores else 0,
            mrr=sum(rr_scores) / len(rr_scores) if rr_scores else 0,
        )

    def _ndcg(self, ranked: List[str], relevant: set, k: int = None) -> float:
        """Normalized Discounted Cumulative Gain"""
        if k:
            ranked = ranked[:k]

        dcg = sum(
            1.0 / math.log2(i + 2)
            for i, c in enumerate(ranked)
            if c.lower() in relevant
        )

        ideal = sum(
            1.0 / math.log2(i + 2)
            for i in range(min(len(relevant), len(ranked)))
        )

        return dcg / ideal if ideal > 0 else 0.0

    # ── H4: Halüsinasyon oranı ─────────────────────────────────────────

    def compare_hallucination_rates(
        self,
        baseline_quarantine: int,
        baseline_total: int,
        system_quarantine: int,
        system_total: int,
    ) -> Dict[str, float]:
        """Baseline vs sistem halüsinasyon oranı karşılaştırması"""
        baseline_rate = baseline_quarantine / baseline_total if baseline_total > 0 else 0
        system_rate = system_quarantine / system_total if system_total > 0 else 0

        reduction = (
            (baseline_rate - system_rate) / baseline_rate * 100
            if baseline_rate > 0
            else 0
        )

        return {
            "baseline_rate": round(baseline_rate * 100, 2),
            "system_rate": round(system_rate * 100, 2),
            "reduction_percent": round(reduction, 2),
            "h4_passed": reduction >= 20.0,
        }

    # ── Ablation Study ─────────────────────────────────────────────────

    def run_ablation_study(
        self,
        cv_texts: List[str],
        query_results_by_config: Dict[str, List[List[str]]],
        gold_relevant: List[List[str]],
        hallucination_data: Dict[str, Tuple[int, int]],
    ) -> List[AblationRow]:
        """
        5 konfigürasyon karşılaştırması:
        BL-1: Sıfır-örnekli, doğrulama yok, sadece Cypher
        BL-2: Few-shot, doğrulama yok, sadece Cypher
        SYS-A: BL-2 + CoT
        SYS-B: SYS-A + RAG doğrulama
        SYS-C: SYS-B + ER + hibrit arama (tam sistem)
        """
        configs = {
            "BL-1": "Sıfır-örnekli prompt, doğrulama yok, sadece Cypher",
            "BL-2": "Few-shot prompt, doğrulama yok, sadece Cypher",
            "SYS-A": "BL-2 + CoT prompting",
            "SYS-B": "SYS-A + RAG doğrulama döngüsü",
            "SYS-C": "SYS-B + Entity Resolution + Hibrit Arama (Tam Sistem)",
        }

        rows = []
        dup_info = self.evaluate_duplicate_rate()

        for config_name, description in configs.items():
            hall_q, hall_t = hallucination_data.get(config_name, (0, 1))
            hall_rate = hall_q / hall_t * 100 if hall_t > 0 else 0

            matching = MatchingResult(0, 0, 0, 0, 0)
            if config_name in query_results_by_config:
                matching = self.evaluate_matching(
                    query_results_by_config[config_name],
                    gold_relevant
                )

            rows.append(AblationRow(
                config=config_name,
                description=description,
                ner_f1=0.0,
                re_f1=0.0,
                hallucination_rate=round(hall_rate, 2),
                ndcg_10=round(matching.ndcg_at_10, 3),
                precision_5=round(matching.precision_at_5, 3),
                duplicate_rate=round(dup_info.get("skill_duplicate_rate", 0), 2),
            ))

        return rows

    # ── Rapor çıktısı ─────────────────────────────────────────────────

    def print_report(
        self,
        ner_results: Dict,
        dup_info: Dict,
        matching: Optional[MatchingResult] = None,
        ablation: Optional[List[AblationRow]] = None
    ):
        """Tüm metrikleri konsola yazdırır"""

        print("\n" + "═" * 60)
        print("  TALENTFORGE DEĞERLENDİRME RAPORU")
        print("═" * 60)

        print("\n📊 H1: Bilgi Çıkarım Kalitesi (NER F1)")
        print("-" * 40)
        for entity_type, result in ner_results.items():
            h1_status = "✅" if result.f1 >= 0.85 else "❌"
            print(f"  {h1_status} {entity_type:15s}: {result}")

        print("\n📊 H2: Duplicate Düğüm Oranı")
        print("-" * 40)
        h2_status = "✅" if dup_info.get("h2_passed") else "❌"
        print(
            f"  {h2_status} Skill duplicates: {dup_info.get('skill_duplicate_rate', '?')}% "
            f"(hedef: ≤5%)"
        )
        print(
            f"     Toplam skill: {dup_info.get('skill_total', '?')} | "
            f"Duplicate: {dup_info.get('skill_duplicates', '?')}"
        )

        if matching:
            print("\n📊 H3 + H5: Eşleştirme Kalitesi")
            print("-" * 40)
            h3_status = "✅" if matching.ndcg_at_10 >= 0.70 else "❌"
            h5_status = "✅" if matching.precision_at_5 >= 0.70 else "❌"
            print(f"  {h3_status} NDCG@10: {matching.ndcg_at_10:.3f} (hedef: ≥0.70)")
            print(f"  {h5_status} Precision@5: {matching.precision_at_5:.3f} (hedef: ≥0.70)")
            print(
                f"     NDCG@5: {matching.ndcg_at_5:.3f} | "
                f"P@10: {matching.precision_at_10:.3f} | MRR: {matching.mrr:.3f}"
            )

        if ablation:
            print("\n📊 Ablation Study")
            print("-" * 60)
            print(f"  {'Konfigürasyon':<10} {'Halüsinasyon':<14} {'NDCG@10':<10} {'P@5':<8}")
            print(f"  {'-'*10} {'-'*14} {'-'*10} {'-'*8}")

            for row in ablation:
                print(
                    f"  {row.config:<10} {row.hallucination_rate:>10.1f}%   "
                    f"{row.ndcg_10:>8.3f}   {row.precision_5:>6.3f}"
                )

        print("\n" + "═" * 60)

    def save_report(
        self,
        output_path: str = "evaluation/results.json",
        ner_results: Dict = None,
        dup_info: Dict = None,
        matching: MatchingResult = None,
        ablation: List[AblationRow] = None
    ):
        """Sonuçları JSON olarak kaydeder"""

        report = {
            "ner": {k: asdict(v) for k, v in (ner_results or {}).items()},
            "duplicate": dup_info or {},
            "matching": asdict(matching) if matching else {},
            "ablation": [asdict(r) for r in (ablation or [])],
        }

        Path(output_path).parent.mkdir(exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ Rapor kaydedildi: {output_path}")