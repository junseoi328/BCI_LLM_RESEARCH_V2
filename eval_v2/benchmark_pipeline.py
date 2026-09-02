from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import unicodedata
from pathlib import Path

from app.llm.fine_tuned_generator_v2 import FineTunedGeneratorClient, load_ft_model
from app.llm.openai_client import OpenAILanguageModelClient
from app.pipeline.service import BCILanguagePipeline
from app.schemas import PredictionRequest
from training_v2.common import load_dotenv_if_available, normalize_text, read_jsonl


def rank_of(target: str, preds: list[str]) -> int | None:
    t = normalize_text(target)
    for i, pred in enumerate(preds, start=1):
        if normalize_text(pred) == t:
            return i
    return None


def run(name: str, pipeline: BCILanguagePipeline, rows: list[dict]) -> dict:
    results = []
    for i, row in enumerate(rows, start=1):
        try:
            res = pipeline.predict(
                PredictionRequest(
                    bci_input=row["bci_input"],
                    partner=row.get("partner","other"),
                    situation=row.get("situation","general"),
                    current_sentence=row.get("current_sentence",""),
                    recent_context=row.get("recent_context",[]),
                    top_k=3,
                )
            )
            preds = [x.text for x in res.candidates]
            rank = rank_of(row["target"], preds)
            results.append(
                {
                    "id":row["id"],
                    "target":row["target"],
                    "preds":preds,
                    "rank":rank,
                    "latency_ms":res.latency.total_ms,
                    "fallback":res.fallback,
                    "error":None,
                }
            )
            print(f"[{name} {i:03d}/{len(rows):03d}] rank={rank} target={row['target']} preds={preds}")
        except Exception as exc:
            results.append(
                {
                    "id":row["id"],
                    "target":row["target"],
                    "preds":[],
                    "rank":None,
                    "latency_ms":None,
                    "fallback":"",
                    "error":f"{type(exc).__name__}:{exc}",
                }
            )
            print(f"[{name} {i:03d}/{len(rows):03d}] ERROR {type(exc).__name__}:{exc}")

    n = len(results)
    ok = [x for x in results if not x["error"]]
    lat = [x["latency_ms"] for x in ok if x["latency_ms"] is not None]
    summary = {
        "arm": name,
        "n": n,
        "acc_at_1": sum(x["rank"] == 1 for x in results) / n if n else 0,
        "acc_at_3": sum(isinstance(x["rank"], int) and x["rank"] <= 3 for x in results) / n if n else 0,
        "mrr": sum((1/x["rank"]) if isinstance(x["rank"], int) else 0 for x in results) / n if n else 0,
        "service_error_rate": sum(bool(x["error"]) for x in results) / n if n else 0,
        "mean_latency_ms": statistics.mean(lat) if lat else None,
    }
    Path(f"eval_v2/reports/{name}_hard50.json").write_text(
        json.dumps({"summary":summary,"rows":results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    load_dotenv_if_available()
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="training_v2/data/hard50_v2.jsonl")
    p.add_argument("--ranker-model", default="gpt-5.6-luna")
    p.add_argument("--base-generator", default="gpt-5.6-luna")
    args = p.parse_args()

    rows = read_jsonl(args.dataset)
    ft_model = load_ft_model()

    # v6.3 조건 유지
    os.environ.setdefault("ENSEMBLE_MODE", "context_quality")
    os.environ.setdefault("ENSEMBLE_MIN_VALID", "6")
    os.environ.setdefault("ENSEMBLE_CONTEXT_THRESHOLD", "0.72")
    os.environ.setdefault("ENSEMBLE_INTENT_THRESHOLD", "0.72")
    os.environ.setdefault("DIVERSITY_GENERATION_COUNT", "8")

    base = BCILanguagePipeline(
        OpenAILanguageModelClient(
            generator_model=args.base_generator,
            ranker_model=args.ranker_model,
        )
    )
    ft = BCILanguagePipeline(
        FineTunedGeneratorClient(
            generator_model=ft_model,
            ranker_model=args.ranker_model,
        )
    )

    s1 = run("v6_3_base", base, rows)
    s2 = run("v7_ft", ft, rows)
    comparison = {
        "base":s1,
        "v7":s2,
        "delta":{
            "acc_at_1":s2["acc_at_1"]-s1["acc_at_1"],
            "acc_at_3":s2["acc_at_3"]-s1["acc_at_3"],
            "mrr":s2["mrr"]-s1["mrr"],
            "mean_latency_ms":(
                None if s1["mean_latency_ms"] is None or s2["mean_latency_ms"] is None
                else s2["mean_latency_ms"]-s1["mean_latency_ms"]
            ),
        },
    }
    Path("eval_v2/reports/pipeline_hard50_comparison.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
