from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

import requests


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
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_json(path: str | Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def expected_names(query: dict[str, Any], key: str) -> set[str]:
    return {
        normalize(item.get("candidate_name"))
        for item in query.get(key, [])
        if normalize(item.get("candidate_name"))
    }


def relevance_for(name: str, strong: set[str], partial: set[str]) -> int:
    if name in strong:
        return 2
    if name in partial:
        return 1
    return 0


def dcg(relevances: list[int]) -> float:
    total = 0.0
    for idx, rel in enumerate(relevances, start=1):
        if rel:
            total += rel / (1 if idx == 1 else __import__("math").log2(idx + 1))
    return total


def evaluate_query(api_base: str, query: dict[str, Any], timeout: int) -> dict[str, Any]:
    started = time.time()
    response = requests.post(
        f"{api_base.rstrip('/')}/nl-search",
        json={"query": query["query_text"]},
        timeout=timeout,
    )
    elapsed = round(time.time() - started, 2)
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results", [])

    strong = expected_names(query, "strong_expected")
    partial = expected_names(query, "partial_expected")
    relevant = strong | partial
    ranked_names = [normalize(item.get("name")) for item in results if normalize(item.get("name"))]
    relevances = [relevance_for(name, strong, partial) for name in ranked_names]

    top1 = ranked_names[:1]
    top3 = ranked_names[:3]
    top5 = ranked_names[:5]
    top10 = ranked_names[:10]
    strong_found_10 = strong & set(top10)
    relevant_found_10 = relevant & set(top10)
    ideal_rels = sorted([2] * len(strong) + [1] * len(partial), reverse=True)[:10]
    ndcg_10 = dcg(relevances[:10]) / dcg(ideal_rels) if ideal_rels and dcg(ideal_rels) else 0.0

    return {
        "query_id": query["query_id"],
        "query_text": query["query_text"],
        "elapsed_sec": elapsed,
        "parsed_query": payload.get("parsed_query", {}),
        "ranked_candidates": [
            {
                "rank": index + 1,
                "candidate_name": item.get("name"),
                "score": item.get("total_score"),
                "relevance": relevance_for(normalize(item.get("name")), strong, partial),
            }
            for index, item in enumerate(results)
        ],
        "strong_expected_count": len(strong),
        "partial_expected_count": len(partial),
        "hit_strong_at_1": bool(strong & set(top1)),
        "hit_strong_at_3": bool(strong & set(top3)),
        "hit_strong_at_5": bool(strong & set(top5)),
        "hit_any_relevant_at_1": bool(relevant & set(top1)),
        "hit_any_relevant_at_3": bool(relevant & set(top3)),
        "hit_any_relevant_at_5": bool(relevant & set(top5)),
        "strong_recall_at_10": len(strong_found_10) / len(strong) if strong else None,
        "relevant_recall_at_10": len(relevant_found_10) / len(relevant) if relevant else None,
        "ndcg_at_10": round(ndcg_10, 4),
    }


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in results if "error" not in r]
    if not ok:
        return {"n_queries": 0, "success_rate": 0.0}

    def avg_bool(key: str) -> float:
        return round(sum(1 for r in ok if r.get(key)) / len(ok), 4)

    def avg_optional(key: str) -> float:
        values = [r[key] for r in ok if r.get(key) is not None]
        return round(sum(values) / len(values), 4) if values else 0.0

    return {
        "n_queries": len(ok),
        "attempted_queries": len(results),
        "success_rate": round(len(ok) / len(results), 4),
        "hit_strong_at_1": avg_bool("hit_strong_at_1"),
        "hit_strong_at_3": avg_bool("hit_strong_at_3"),
        "hit_strong_at_5": avg_bool("hit_strong_at_5"),
        "hit_any_relevant_at_1": avg_bool("hit_any_relevant_at_1"),
        "hit_any_relevant_at_3": avg_bool("hit_any_relevant_at_3"),
        "hit_any_relevant_at_5": avg_bool("hit_any_relevant_at_5"),
        "strong_recall_at_10": avg_optional("strong_recall_at_10"),
        "relevant_recall_at_10": avg_optional("relevant_recall_at_10"),
        "ndcg_at_10": avg_optional("ndcg_at_10"),
        "avg_elapsed_sec": round(sum(r.get("elapsed_sec", 0.0) for r in ok) / len(ok), 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", default="evaluation/matching_ground_truth.json")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--output", default="evaluation/thesis_outputs/matching_results.json")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    queries = load_json(args.ground_truth)
    results = []
    for index, query in enumerate(queries, start=1):
        print(f"[{index}/{len(queries)}] {query['query_id']}")
        try:
            results.append(evaluate_query(args.api_base, query, args.timeout))
        except Exception as exc:
            results.append({
                "query_id": query.get("query_id"),
                "query_text": query.get("query_text"),
                "error": str(exc),
            })

    payload = {"aggregate": aggregate(results), "queries": results}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("\nMatching evaluation")
    print("=" * 72)
    for key, value in payload["aggregate"].items():
        print(f"{key:<26} {value}")
    print(f"\nSaved: {output}")


if __name__ == "__main__":
    main()
