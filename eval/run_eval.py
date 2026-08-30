from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path

from app.errors import LLMServiceError
from app.korean.initials import extract_initials
from app.pipeline.diversity import text_similarity
from app.pipeline.service import BCILanguagePipeline
from app.schemas import ContextLevel, PredictionRequest
from eval.metrics import summarize

ROOT = Path(__file__).resolve().parent


def load_dataset(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def classify_failure(target: str, preds: list[str]) -> str:
    if not preds:
        return "E02_NO_VALID_CANDIDATE"
    if target in preds[:3]:
        if len(preds) >= 2 and text_similarity(preds[0], preds[1]) >= 0.90:
            return "E04_SEMANTIC_DUPLICATE"
        return "OK"
    if target in preds:
        return "TARGET_BELOW_TOP3"
    return "E03_CONTEXT_OR_GENERATION_MISS"


def service_failure_type(code: str) -> str:
    if code == "timeout":
        return "E07_LLM_TIMEOUT"
    if code == "connection_error":
        return "E12_NETWORK_ERROR"
    if code in {"rate_limit", "insufficient_quota", "project_spend_limit_exceeded", "organization_limit_exceeded"}:
        return "E13_API_LIMIT"
    if code in {"incomplete_max_output_tokens", "malformed_structured_output", "empty_structured_output", "incomplete_response"}:
        return "E15_STRUCTURED_OUTPUT_FAILURE"
    return "E14_LLM_SERVICE_ERROR"


def evaluate(dataset_path: Path, context_level: ContextLevel, limit: int | None = None) -> tuple[list[dict], dict]:
    source_rows = load_dataset(dataset_path)
    if limit:
        source_rows = source_rows[:limit]

    pipeline = BCILanguagePipeline()
    results: list[dict] = []

    for i, row in enumerate(source_rows, start=1):
        target = row["target"]
        bci_input = row.get("bci_input") or extract_initials(target)
        req = PredictionRequest(
            trial_id=row.get("id", f"T{i:03d}"),
            bci_input=bci_input,
            partner=row.get("partner", "other"),
            situation=row.get("situation", "general"),
            current_sentence=row.get("current_sentence", ""),
            recent_context=row.get("recent_context", []),
            context_level=context_level,
            top_k=3,
        )

        wall_start = time.perf_counter()
        try:
            response = pipeline.predict(req)
        except LLMServiceError as exc:
            elapsed_ms = int((time.perf_counter() - wall_start) * 1000)
            result = {
                "id": row.get("id", f"T{i:03d}"),
                "target": target,
                "bci_input": bci_input,
                "partner": row.get("partner", "other"),
                "situation": row.get("situation", "general"),
                "context_level": context_level.value,
                "pred_1": "",
                "pred_2": "",
                "pred_3": "",
                "target_rank": None,
                "latency_ms": elapsed_ms,
                "fallback": "service_error",
                "generator_model": getattr(pipeline.model_client, "generator_model_name", ""),
                "ranker_model": getattr(pipeline.model_client, "ranker_model_name", ""),
                "estimated_cost_usd": None,
                "failure_type": service_failure_type(exc.code),
                "service_error_code": exc.code,
            }
            results.append(result)
            print(
                f"[{i:03d}/{len(source_rows):03d}] {bci_input} target={target} "
                f"ERROR={exc.code} latency={elapsed_ms}ms"
            )
            continue

        preds = [c.text for c in response.candidates]
        target_rank = preds.index(target) + 1 if target in preds else None
        result = {
            "id": row.get("id", f"T{i:03d}"),
            "target": target,
            "bci_input": bci_input,
            "partner": row.get("partner", "other"),
            "situation": row.get("situation", "general"),
            "context_level": context_level.value,
            "pred_1": preds[0] if len(preds) > 0 else "",
            "pred_2": preds[1] if len(preds) > 1 else "",
            "pred_3": preds[2] if len(preds) > 2 else "",
            "target_rank": target_rank,
            "latency_ms": response.latency.total_ms,
            "fallback": response.fallback,
            "generator_model": response.generator_model,
            "ranker_model": response.ranker_model,
            "estimated_cost_usd": response.usage.estimated_cost_usd,
            "failure_type": classify_failure(target, preds),
            "service_error_code": "",
        }
        results.append(result)
        print(f"[{i:03d}/{len(source_rows):03d}] {bci_input} target={target} preds={preds} rank={target_rank}")

    return results, summarize(results)


def write_report(results: list[dict], summary: dict, prefix: Path) -> None:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    csv_path = prefix.with_suffix(".csv")
    json_path = prefix.with_suffix(".summary.json")

    if results:
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"CSV: {csv_path}")
    print(f"Summary: {json_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(ROOT / "datasets" / "sanity_v1.jsonl"))
    parser.add_argument("--context-level", choices=[x.value for x in ContextLevel], default="full")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    level = ContextLevel(args.context_level)
    results, summary = evaluate(dataset_path, level, args.limit)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = Path(args.output) if args.output else ROOT / "reports" / f"eval_{level.value}_{stamp}"
    write_report(results, summary, output)


if __name__ == "__main__":
    main()
