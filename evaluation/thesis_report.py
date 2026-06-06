from __future__ import annotations

import argparse
import csv
import json
import math
import textwrap
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover - runtime dependency guard for thesis artifact generation
    Image = ImageDraw = ImageFont = None


PALETTE = ["#ff315d", "#a855f7", "#22c55e", "#38bdf8", "#facc15", "#fb923c", "#e879f9"]
BG = "#101014"
PANEL = "#171720"
TEXT = "#f8fafc"
MUTED = "#b8b8c8"
GRID = "#30303d"


def load_json(path: str | Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def maybe_load(path: str | Path | None) -> Any | None:
    if not path:
        return None
    p = Path(path)
    return load_json(p) if p.exists() else None


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if ImageFont is None:
        raise RuntimeError("Pillow is required for JPEG figure generation.")
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def save_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    headers = list(rows[0].keys())
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    return "\n".join(lines)


def aggregate_rows(ablation: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for run_key, run_data in sorted(ablation.items()):
        agg = run_data.get("aggregate", {})
        if not agg:
            continue
        rows.append({
            "run": run_key,
            "config": run_data.get("config"),
            "model": run_data.get("model"),
            "n": agg.get("n_cvs", 0),
            "success_rate": agg.get("success_rate", 0),
            "ner_f1": agg.get("avg_overall_ner_f1", 0),
            "skill_f1": agg.get("avg_skill_f1", 0),
            "re_f1": agg.get("avg_re_f1", 0),
            "kg_f1": agg.get("kg_triple_f1", 0),
            "hallucination_rate": agg.get("avg_hallucination_rate", 0),
            "unsupported_triple_rate": agg.get("avg_unsupported_triple_rate", 0),
            "avg_elapsed_sec": agg.get("avg_elapsed_sec", 0),
        })
    return rows


def triple_relation_rows(triple: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not triple:
        return []
    runs = triple.get("runs", {})
    rows = []
    for run_key, run_data in sorted(runs.items()):
        for relation, metrics in sorted(run_data.get("by_relation", {}).items()):
            rows.append({
                "run": run_key,
                "relation": relation,
                "precision": metrics.get("precision", 0),
                "recall": metrics.get("recall", 0),
                "f1": metrics.get("f1", 0),
                "tp": metrics.get("true_positives", 0),
                "fp": metrics.get("false_positives", 0),
                "fn": metrics.get("false_negatives", 0),
            })
    return rows


def metadata_rows(triple: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not triple:
        return []
    rows = []
    for run_key, run_data in sorted(triple.get("runs", {}).items()):
        for field, values in sorted(run_data.get("by_metadata", {}).items()):
            for value, metrics in sorted(values.items()):
                rows.append({
                    "run": run_key,
                    "metadata_field": field,
                    "value": value,
                    "precision": metrics.get("precision", 0),
                    "recall": metrics.get("recall", 0),
                    "f1": metrics.get("f1", 0),
                })
    return rows


def distribution_rows(dataset_summary: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not dataset_summary:
        return []
    wanted = [
        "format_distribution",
        "language_distribution",
        "difficulty_distribution",
        "template_distribution",
        "role_family_distribution",
        "title_group_distribution",
    ]
    rows = []
    for section in wanted:
        for key, value in dataset_summary.get(section, {}).items():
            rows.append({"section": section, "value": key, "count": value})
    return rows


def draw_bar_chart(
    path: Path,
    title: str,
    labels: list[str],
    values: list[float],
    *,
    subtitle: str = "",
    percent: bool = False,
    width: int = 1400,
    height: int = 850,
) -> None:
    if Image is None or ImageDraw is None:
        raise RuntimeError("Pillow is required for JPEG figure generation.")
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)
    title_font = font(44, True)
    label_font = font(22)
    small_font = font(18)
    draw.text((55, 40), title, fill=TEXT, font=title_font)
    if subtitle:
        draw.text((58, 96), subtitle, fill=MUTED, font=small_font)

    left, top, right, bottom = 90, 165, width - 65, height - 155
    draw.rounded_rectangle((35, 130, width - 35, height - 40), radius=18, fill=PANEL, outline="#262633")
    max_value = max(values) if values else 1.0
    max_value = 1.0 if percent else max(max_value, 1.0)

    for i in range(6):
        y = bottom - (bottom - top) * i / 5
        draw.line((left, y, right, y), fill=GRID, width=1)
        tick = max_value * i / 5
        tick_label = f"{tick:.0%}" if percent else f"{tick:.2f}"
        draw.text((30, y - 11), tick_label, fill=MUTED, font=small_font)

    n = max(len(values), 1)
    slot = (right - left) / n
    bar_width = min(90, slot * 0.55)
    for index, (label, value) in enumerate(zip(labels, values)):
        x0 = left + slot * index + (slot - bar_width) / 2
        x1 = x0 + bar_width
        y1 = bottom
        y0 = bottom - (bottom - top) * (value / max_value if max_value else 0)
        color = PALETTE[index % len(PALETTE)]
        draw.rounded_rectangle((x0, y0, x1, y1), radius=10, fill=color)
        value_label = f"{value:.1%}" if percent else f"{value:.3f}"
        draw.text((x0 - 8, y0 - 30), value_label, fill=TEXT, font=small_font)
        wrapped = textwrap.wrap(label, width=16)[:3]
        for line_idx, line in enumerate(wrapped):
            draw.text((x0 - 28, bottom + 18 + line_idx * 22), line, fill=MUTED, font=small_font)

    image.save(path, quality=95)


def draw_grouped_metrics(path: Path, rows: list[dict[str, Any]]) -> None:
    if Image is None or ImageDraw is None:
        raise RuntimeError("Pillow is required for JPEG figure generation.")
    metrics = ["ner_f1", "skill_f1", "re_f1", "kg_f1"]
    labels = [row["run"] for row in rows]
    width, height = 1700, 900
    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)
    draw.text((55, 40), "Ablation / Model Metrik Karsilastirmasi", fill=TEXT, font=font(42, True))
    draw.text((58, 94), "NER, skill extraction, relation extraction ve KG triple F1", fill=MUTED, font=font(20))
    draw.rounded_rectangle((35, 130, width - 35, height - 45), radius=18, fill=PANEL, outline="#262633")

    left, top, right, bottom = 100, 180, width - 80, height - 180
    for i in range(6):
        y = bottom - (bottom - top) * i / 5
        draw.line((left, y, right, y), fill=GRID, width=1)
        draw.text((38, y - 11), f"{i / 5:.1f}", fill=MUTED, font=font(18))

    group_slot = (right - left) / max(len(rows), 1)
    bar_width = min(34, group_slot / (len(metrics) + 1.5))
    for group_idx, row in enumerate(rows):
        base_x = left + group_slot * group_idx + group_slot * 0.16
        for metric_idx, metric in enumerate(metrics):
            value = float(row.get(metric, 0) or 0)
            x0 = base_x + metric_idx * (bar_width + 8)
            x1 = x0 + bar_width
            y0 = bottom - (bottom - top) * min(value, 1.0)
            draw.rounded_rectangle((x0, y0, x1, bottom), radius=7, fill=PALETTE[metric_idx])
        wrapped = textwrap.wrap(row["run"], width=18)[:3]
        for line_idx, line in enumerate(wrapped):
            draw.text((base_x - 18, bottom + 18 + line_idx * 22), line, fill=MUTED, font=font(17))

    legend_x = width - 560
    for idx, metric in enumerate(metrics):
        x = legend_x + idx * 130
        draw.rounded_rectangle((x, 92, x + 24, 116), radius=5, fill=PALETTE[idx])
        draw.text((x + 32, 91), metric, fill=TEXT, font=font(18))
    image.save(path, quality=95)


def draw_table_image(path: Path, title: str, rows: list[dict[str, Any]], max_rows: int = 12) -> None:
    if Image is None or ImageDraw is None:
        raise RuntimeError("Pillow is required for JPEG figure generation.")
    shown = rows[:max_rows]
    if not shown:
        return
    headers = list(shown[0].keys())
    width = 1800
    row_h = 54
    height = 160 + row_h * (len(shown) + 1)
    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)
    draw.text((45, 35), title, fill=TEXT, font=font(40, True))
    x_positions = [45, 390, 560, 700, 840, 980, 1120, 1260, 1400, 1540]
    y = 115
    draw.rounded_rectangle((25, 90, width - 25, height - 25), radius=14, fill=PANEL, outline="#262633")
    for idx, header in enumerate(headers[: len(x_positions)]):
        draw.text((x_positions[idx], y), header, fill="#d9f99d", font=font(18, True))
    y += row_h
    for row in shown:
        draw.line((35, y - 12, width - 35, y - 12), fill=GRID, width=1)
        for idx, header in enumerate(headers[: len(x_positions)]):
            text = str(row.get(header, ""))
            draw.text((x_positions[idx], y), text[:32], fill=TEXT, font=font(17))
        y += row_h
    image.save(path, quality=95)


def matching_rows(matching: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not matching:
        return []
    agg = matching.get("aggregate", {})
    return [
        {"metric": key, "value": value}
        for key, value in agg.items()
        if isinstance(value, (int, float))
    ]


def entity_resolution_rows(er: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not er:
        return []
    agg = er.get("aggregate", {})
    return [
        {"metric": key, "value": value}
        for key, value in agg.items()
        if isinstance(value, (int, float))
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ablation", default="evaluation/ablation_results_thesis_100.json")
    parser.add_argument("--triple", default="evaluation/ablation_triple_results_thesis_100.json")
    parser.add_argument("--dataset-summary", default="evaluation/dataset_summary.json")
    parser.add_argument("--matching", default="evaluation/thesis_outputs/matching_results.json")
    parser.add_argument("--entity-resolution", default="evaluation/thesis_outputs/entity_resolution_results.json")
    parser.add_argument("--output-dir", default="evaluation/thesis_outputs")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ablation = load_json(args.ablation)
    triple = maybe_load(args.triple)
    dataset_summary = maybe_load(args.dataset_summary)
    matching = maybe_load(args.matching)
    entity_resolution = maybe_load(args.entity_resolution)

    aggregates = aggregate_rows(ablation)
    relations = triple_relation_rows(triple)
    metadata = metadata_rows(triple)
    distributions = distribution_rows(dataset_summary)
    match_rows = matching_rows(matching)
    er_rows = entity_resolution_rows(entity_resolution)

    save_csv(output_dir / "ablation_aggregate_metrics.csv", aggregates)
    save_csv(output_dir / "kg_relation_metrics.csv", relations)
    save_csv(output_dir / "kg_metadata_breakdowns.csv", metadata)
    save_csv(output_dir / "dataset_distributions.csv", distributions)
    save_csv(output_dir / "matching_metrics.csv", match_rows)
    save_csv(output_dir / "entity_resolution_metrics.csv", er_rows)

    figure_errors = []
    try:
        if aggregates:
            draw_grouped_metrics(output_dir / "ablation_model_metrics.jpeg", aggregates)
            draw_bar_chart(
                output_dir / "hallucination_rates.jpeg",
                "Unsupported / Hallucination Rate",
                [row["run"] for row in aggregates],
                [float(row["hallucination_rate"] or 0) for row in aggregates],
                percent=True,
            )
            draw_table_image(output_dir / "ablation_summary_table.jpeg", "Ablation Summary", aggregates)

        if relations:
            best_run = aggregates[0]["run"] if len(aggregates) == 1 else max(aggregates, key=lambda r: r["kg_f1"])["run"]
            rel_for_best = [row for row in relations if row["run"] == best_run]
            draw_bar_chart(
                output_dir / "kg_relation_f1.jpeg",
                f"KG Relation F1 - {best_run}",
                [row["relation"] for row in rel_for_best],
                [float(row["f1"] or 0) for row in rel_for_best],
            )

        if dataset_summary:
            for section in ["role_family_distribution", "difficulty_distribution", "template_distribution"]:
                dist = dataset_summary.get(section, {})
                if dist:
                    draw_bar_chart(
                        output_dir / f"{section}.jpeg",
                        section.replace("_", " ").title(),
                        list(dist.keys()),
                        [float(v) for v in dist.values()],
                        subtitle=f"Total CV: {dataset_summary.get('total_cvs', '')}",
                    )

        if match_rows:
            selected = [
                row for row in match_rows
                if row["metric"] in {
                    "hit_strong_at_1",
                    "hit_strong_at_3",
                    "hit_strong_at_5",
                    "relevant_recall_at_10",
                    "ndcg_at_10",
                }
            ]
            draw_bar_chart(
                output_dir / "matching_metrics.jpeg",
                "Candidate Matching Metrics",
                [row["metric"] for row in selected],
                [float(row["value"] or 0) for row in selected],
            )

        if er_rows:
            selected_er = [
                row for row in er_rows
                if row["metric"] in {"merge_success_rate", "skill_node_count", "company_node_count"}
            ]
            draw_bar_chart(
                output_dir / "entity_resolution_metrics.jpeg",
                "Entity Resolution Metrics",
                [row["metric"] for row in selected_er],
                [float(row["value"] or 0) for row in selected_er],
            )
    except Exception as exc:
        figure_errors.append(str(exc))

    summary = [
        "# TalentForge Thesis Evaluation Outputs",
        "",
        "## Ablation / Model Results",
        markdown_table(aggregates),
        "",
        "## Matching Metrics",
        markdown_table(match_rows),
        "",
        "## Entity Resolution Metrics",
        markdown_table(er_rows),
        "",
        "## Generated Figures",
    ]
    for image_path in sorted(output_dir.glob("*.jpeg")):
        summary.append(f"- `{image_path.name}`")
    if figure_errors:
        summary.extend(["", "## Figure Generation Warning", *[f"- {error}" for error in figure_errors]])
    (output_dir / "thesis_report_summary.md").write_text("\n".join(summary), encoding="utf-8")

    print(f"Thesis report artifacts saved to: {output_dir}")


if __name__ == "__main__":
    main()
