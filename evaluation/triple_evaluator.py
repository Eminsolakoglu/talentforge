"""
Triple-level evaluation for LLM-based knowledge graph construction.

This module evaluates whether extracted CV records can construct the expected
HR knowledge graph triples, independent from Neo4j runtime state.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Triple:
    subject: str
    relation: str
    object: str


@dataclass
class PRF:
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int


@dataclass
class TripleEvaluationReport:
    overall: PRF
    by_relation: dict[str, PRF]
    by_metadata: dict[str, dict[str, PRF]]
    total_gold_triples: int
    total_pred_triples: int
    total_records: int


def normalize(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.lower().strip()
    tr_map = str.maketrans({
        "ı": "i",
        "İ": "i",
        "ğ": "g",
        "ü": "u",
        "ş": "s",
        "ö": "o",
        "ç": "c",
    })
    text = text.translate(tr_map)
    text = re.sub(r"[^a-z0-9+#./ -]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def canonical_candidate(record: dict[str, Any]) -> str:
    return normalize(record.get("candidate_name") or record.get("name") or "candidate")


def make_triples(record: dict[str, Any]) -> set[Triple]:
    candidate = canonical_candidate(record)
    triples: set[Triple] = set()

    for skill in record.get("skills", []) or []:
        skill_name = skill.get("name") if isinstance(skill, dict) else skill
        if normalize(skill_name):
            triples.add(Triple(candidate, "HAS_SKILL", normalize(skill_name)))

    for exp in record.get("experiences", []) or []:
        company = normalize(exp.get("company_name"))
        role = normalize(exp.get("role_title"))
        exp_node = normalize(f"{role} at {company}") if role or company else ""

        if exp_node:
            triples.add(Triple(candidate, "HAS_EXPERIENCE", exp_node))
        if exp_node and company:
            triples.add(Triple(exp_node, "AT_COMPANY", company))
        for skill in exp.get("skills_used", []) or []:
            if exp_node and normalize(skill):
                triples.add(Triple(exp_node, "USED_SKILL", normalize(skill)))

    for edu in record.get("educations", []) or []:
        degree = normalize(edu.get("degree"))
        field = normalize(edu.get("field"))
        institution = normalize(edu.get("institution"))
        education_node = normalize(f"{degree} {field}") if degree or field else ""

        if education_node:
            triples.add(Triple(candidate, "HAS_EDUCATION", education_node))
        if education_node and institution:
            triples.add(Triple(education_node, "AT_INSTITUTION", institution))

    for language in record.get("languages", []) or []:
        if normalize(language):
            triples.add(Triple(candidate, "SPEAKS", normalize(language)))

    for cert in record.get("certifications", []) or []:
        if normalize(cert):
            triples.add(Triple(candidate, "HAS_CERTIFICATION", normalize(cert)))

    for project in record.get("projects", []) or []:
        if not isinstance(project, dict):
            continue
        project_name = normalize(project.get("name"))
        if not project_name:
            continue
        triples.add(Triple(candidate, "HAS_PROJECT", project_name))
        for skill in project.get("skills_used", []) or []:
            if normalize(skill):
                triples.add(Triple(project_name, "PROJECT_USED_SKILL", normalize(skill)))

    return triples


def compute_prf(pred: set[Triple], gold: set[Triple]) -> PRF:
    tp = len(pred & gold)
    fp = len(pred - gold)
    fn = len(gold - pred)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return PRF(
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
    )


def _group_by_relation(triples: set[Triple]) -> dict[str, set[Triple]]:
    grouped: dict[str, set[Triple]] = defaultdict(set)
    for triple in triples:
        grouped[triple.relation].add(triple)
    return grouped


def evaluate_triples(
    predictions: list[dict[str, Any]],
    gold_items: list[dict[str, Any]],
    metadata_fields: list[str] | None = None,
) -> TripleEvaluationReport:
    metadata_fields = metadata_fields or [
        "difficulty",
        "file_format",
        "cv_language",
        "template_type",
        "role_family",
        "seniority",
        "title_group",
    ]

    total_pred: set[Triple] = set()
    total_gold: set[Triple] = set()
    relation_pred: dict[str, set[Triple]] = defaultdict(set)
    relation_gold: dict[str, set[Triple]] = defaultdict(set)
    metadata_pred: dict[str, dict[str, set[Triple]]] = defaultdict(lambda: defaultdict(set))
    metadata_gold: dict[str, dict[str, set[Triple]]] = defaultdict(lambda: defaultdict(set))

    for index, gold in enumerate(gold_items):
        pred = predictions[index] if index < len(predictions) else {}
        pred_triples = make_triples(pred)
        gold_triples = make_triples(gold)

        total_pred |= pred_triples
        total_gold |= gold_triples

        for relation, triples in _group_by_relation(pred_triples).items():
            relation_pred[relation] |= triples
        for relation, triples in _group_by_relation(gold_triples).items():
            relation_gold[relation] |= triples

        for field in metadata_fields:
            value = str(gold.get(field, "unknown") or "unknown")
            metadata_pred[field][value] |= pred_triples
            metadata_gold[field][value] |= gold_triples

    all_relations = sorted(set(relation_pred) | set(relation_gold))
    by_relation = {
        relation: compute_prf(relation_pred[relation], relation_gold[relation])
        for relation in all_relations
    }

    by_metadata = {}
    for field in metadata_fields:
        values = sorted(set(metadata_pred[field]) | set(metadata_gold[field]))
        by_metadata[field] = {
            value: compute_prf(metadata_pred[field][value], metadata_gold[field][value])
            for value in values
        }

    return TripleEvaluationReport(
        overall=compute_prf(total_pred, total_gold),
        by_relation=by_relation,
        by_metadata=by_metadata,
        total_gold_triples=len(total_gold),
        total_pred_triples=len(total_pred),
        total_records=len(gold_items),
    )


def load_json(path: str | Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def print_report(report: TripleEvaluationReport) -> None:
    print("\n" + "=" * 86)
    print("  TRIPLE-LEVEL KNOWLEDGE GRAPH CONSTRUCTION EVALUATION")
    print("=" * 86)
    print(
        f"Overall: P={report.overall.precision:.3f} "
        f"R={report.overall.recall:.3f} "
        f"F1={report.overall.f1:.3f} "
        f"(TP={report.overall.true_positives} "
        f"FP={report.overall.false_positives} "
        f"FN={report.overall.false_negatives})"
    )
    print(f"Gold triples: {report.total_gold_triples} | Pred triples: {report.total_pred_triples}")

    print("\nBy relation")
    print(f"{'Relation':<20} {'P':>7} {'R':>7} {'F1':>7} {'TP':>6} {'FP':>6} {'FN':>6}")
    print("-" * 66)
    for relation, score in report.by_relation.items():
        print(
            f"{relation:<20} {score.precision:>7.3f} {score.recall:>7.3f} "
            f"{score.f1:>7.3f} {score.true_positives:>6} "
            f"{score.false_positives:>6} {score.false_negatives:>6}"
        )

    print("\nBy difficulty")
    print(f"{'Value':<16} {'P':>7} {'R':>7} {'F1':>7} {'TP':>6} {'FP':>6} {'FN':>6}")
    print("-" * 62)
    for value, score in report.by_metadata.get("difficulty", {}).items():
        print(
            f"{value:<16} {score.precision:>7.3f} {score.recall:>7.3f} "
            f"{score.f1:>7.3f} {score.true_positives:>6} "
            f"{score.false_positives:>6} {score.false_negatives:>6}"
        )
    print("=" * 86)


def save_report(report: TripleEvaluationReport, output_path: str | Path) -> None:
    payload = asdict(report)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", default="evaluation/golden_extractions_pretty.json")
    parser.add_argument("--predictions", default=None)
    parser.add_argument("--output", default="evaluation/triple_results.json")
    args = parser.parse_args()

    gold = load_json(args.gold)
    predictions = load_json(args.predictions) if args.predictions else gold
    report = evaluate_triples(predictions, gold)
    print_report(report)
    save_report(report, args.output)
    print(f"\nSaved: {args.output}")


if __name__ == "__main__":
    main()
