from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from app.config import settings
from app.llm.openai_client import OpenAILanguageModelClient
from app.pipeline.service import BCILanguagePipeline
from app.schemas import ContextLevel, PredictionRequest
from app.korean.initials import extract_initials
from eval.metrics import summarize
from eval.run_eval import load_dataset

ROOT = Path(__file__).resolve().parent


def eval_model(model: str, dataset: Path, limit: int | None) -> dict:
    if settings.mock_mode:
        raise RuntimeError("Model benchmark는 .env에서 MOCK_MODE=false로 설정한 뒤 실행하세요.")
    rows = load_dataset(dataset)
    if limit:
        rows = rows[:limit]
    client = OpenAILanguageModelClient(generator_model=model, ranker_model=model)
    pipeline = BCILanguagePipeline(model_client=client)
    results = []
    for i, row in enumerate(rows, 1):
        target = row["target"]
        req = PredictionRequest(
            bci_input=row.get("bci_input") or extract_initials(target),
            partner=row.get("partner", "other"),
            situation=row.get("situation", "general"),
            current_sentence=row.get("current_sentence", ""),
            recent_context=row.get("recent_context", []),
            context_level=ContextLevel.full,
            top_k=3,
        )
        res = pipeline.predict(req)
        preds = [c.text for c in res.candidates]
        results.append({
            "target_rank": preds.index(target) + 1 if target in preds else None,
            "latency_ms": res.latency.total_ms,
            "estimated_cost_usd": res.usage.estimated_cost_usd,
            "fallback": res.fallback,
        })
        print(f"{model} [{i}/{len(rows)}] {target} -> {preds}")
    return summarize(results)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(ROOT / "datasets" / "sanity_v1.jsonl"))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--models", nargs="+", default=["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"])
    args = parser.parse_args()

    report = {model: eval_model(model, Path(args.dataset), args.limit) for model in args.models}
    out = ROOT / "reports" / "model_benchmark_latest.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
