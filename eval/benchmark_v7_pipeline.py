from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics
import time
import unicodedata
from pathlib import Path

from app.llm.enhanced_client import EnhancedLanguageModelClient
from app.llm.openai_client import OpenAILanguageModelClient
from app.pipeline.service import BCILanguagePipeline
from app.schemas import PredictionRequest

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def normalize_eval_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").strip()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"""[.,!?~…'"“”‘’·:;()\[\]{}<>]""", "", text)
    return text


def load_dataset(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def rank_of(target: str, preds: list[str]) -> int | None:
    t = normalize_eval_text(target)
    for i, pred in enumerate(preds, start=1):
        if normalize_eval_text(pred) == t:
            return i
    return None


def make_request(row: dict) -> PredictionRequest:
    return PredictionRequest(
        bci_input=row["bci_input"],
        partner=row.get("partner", "other"),
        situation=row.get("situation", "general"),
        current_sentence=row.get("current_sentence", ""),
        recent_context=row.get("recent_context", []),
        top_k=3,
    )


def run_arm(name: str, pipeline: BCILanguagePipeline, rows: list[dict], limit: int | None):
    if limit:
        rows = rows[:limit]

    results = []
    for i, row in enumerate(rows, start=1):
        try:
            res = pipeline.predict(make_request(row))
            preds = [x.text for x in res.candidates]
            rank = rank_of(row["target"], preds)
            results.append(
                {
                    "id": row.get("id", f"T{i:03d}"),
                    "target": row["target"],
                    "bci_input": row["bci_input"],
                    "pred_1": preds[0] if len(preds) > 0 else "",
                    "pred_2": preds[1] if len(preds) > 1 else "",
                    "pred_3": preds[2] if len(preds) > 2 else "",
                    "rank": rank,
                    "latency_ms": res.latency.total_ms,
                    "fallback": res.fallback,
                    "service_error": False,
                }
            )
            print(f"[{name} {i:03d}/{len(rows):03d}] rank={rank} target={row['target']} preds={preds}")
        except Exception as exc:
            results.append(
                {
                    "id": row.get("id", f"T{i:03d}"),
                    "target": row["target"],
                    "bci_input": row["bci_input"],
                    "pred_1": "",
                    "pred_2": "",
                    "pred_3": "",
                    "rank": None,
                    "latency_ms": None,
                    "fallback": "",
                    "service_error": True,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            print(f"[{name} {i:03d}/{len(rows):03d}] ERROR {type(exc).__name__}: {exc}")

    n = len(results)
    ok = [r for r in results if not r["service_error"]]
    lat = [r["latency_ms"] for r in ok if r["latency_ms"] is not None]
    summary = {
        "name": name,
        "n": n,
        "acc_at_1": sum(r["rank"] == 1 for r in results) / n if n else 0,
        "acc_at_3": sum(isinstance(r["rank"], int) and r["rank"] <= 3 for r in results) / n if n else 0,
        "mrr": sum((1/r["rank"]) if isinstance(r["rank"], int) else 0 for r in results) / n if n else 0,
        "service_error_rate": sum(r["service_error"] for r in results) / n if n else 0,
        "fallback_rate": sum(r.get("fallback") not in {"", "none", None} for r in ok) / len(ok) if ok else 0,
        "mean_latency_ms": statistics.mean(lat) if lat else None,
    }
    return results, summary


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    keys = sorted({k for row in rows for k in row})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="eval/datasets/test_v1_150.jsonl")
    p.add_argument("--model-state", default="training/artifacts/ft_model.json")
    p.add_argument("--ranker-model", default="gpt-5.6-luna")
    p.add_argument("--baseline-generator", default="gpt-5.6-luna")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--final-test", action="store_true")
    args = p.parse_args()

    if "test" in Path(args.dataset).name.lower() and not args.final_test:
        raise SystemExit(
            "STOP: TEST 데이터는 모델/설정 선택에 사용하면 안 됩니다.\n"
            "정말 최종 고정 평가를 한 번 실행하려면 --final-test를 명시하세요."
        )

    state = json.loads(Path(args.model_state).read_text(encoding="utf-8"))
    ft_model = state["fine_tuned_model"]
    rows = load_dataset(Path(args.dataset))

    # 현재 v6.3 setting을 유지.
    os.environ.setdefault("ENSEMBLE_MODE", "context_quality")
    os.environ.setdefault("ENSEMBLE_MIN_VALID", "6")
    os.environ.setdefault("ENSEMBLE_CONTEXT_THRESHOLD", "0.72")
    os.environ.setdefault("ENSEMBLE_INTENT_THRESHOLD", "0.72")
    os.environ.setdefault("DIVERSITY_GENERATION_COUNT", "8")

    baseline_client = OpenAILanguageModelClient(
        generator_model=args.baseline_generator,
        ranker_model=args.ranker_model,
    )
    ft_client = EnhancedLanguageModelClient(
        generator_model=ft_model,
        ranker_model=args.ranker_model,
        phrase_bank_path="research/phrase_memory/common_phrase_bank.jsonl",
    )

    arms = [
        ("v6_3_luna", BCILanguagePipeline(baseline_client)),
        ("v7_ft_plus_memory", BCILanguagePipeline(ft_client)),
    ]

    out_dir = Path("eval/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries = []

    for name, pipeline in arms:
        result, summary = run_arm(name, pipeline, rows, args.limit)
        write_csv(out_dir / f"{name}_benchmark.csv", result)
        (out_dir / f"{name}_benchmark.summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        summaries.append(summary)

    print("\n=== PAIR SUMMARY ===")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
