from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from app.pipeline.service import BCILanguagePipeline
from app.schemas import PredictionRequest


def normalize_eval_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").strip()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"""[.,!?~…'"“”‘’·:;()\[\]{}<>]""", "", text)
    return text


def rank_of(target: str, preds: list[str], normalized: bool = False):
    if normalized:
        t = normalize_eval_text(target)
        for i, p in enumerate(preds, 1):
            if normalize_eval_text(p) == t:
                return i
        return None
    for i, p in enumerate(preds, 1):
        if p == target:
            return i
    return None


def percentile(values: list[float], p: float):
    if not values:
        return None
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    k = (len(vals) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(vals) - 1)
    frac = k - lo
    return vals[lo] * (1 - frac) + vals[hi] * frac


def load_dataset(path: Path):
    out = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def evaluate(dataset: Path, label: str, limit: int | None = None):
    cases = load_dataset(dataset)
    if limit:
        cases = cases[:limit]

    pipeline = BCILanguagePipeline()
    report_dir = Path("eval/reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", label)
    csv_path = report_dir / f"test_v1_{safe_label}_{stamp}.csv"
    summary_path = report_dir / f"test_v1_{safe_label}_{stamp}.summary.json"

    rows = []
    latencies = []
    costs = []
    strict_ranks = []
    norm_ranks = []
    fallback_count = 0
    error_count = 0

    for i, case in enumerate(cases, 1):
        started = time.perf_counter()
        error_code = ""
        preds = []
        fallback = "error"
        cost = 0.0

        try:
            res = pipeline.predict(
                PredictionRequest(
                    bci_input=case["bci_input"],
                    partner=case["partner"],
                    situation=case["situation"],
                    current_sentence=case.get("current_sentence", ""),
                    recent_context=case.get("recent_context", []),
                    top_k=int(case.get("top_k", 3)),
                )
            )
            preds = [x.text for x in res.candidates]
            latency = float(res.latency.total_ms)
            fallback = str(res.fallback)
            usage = getattr(res, "usage", None)
            if usage:
                cost = float(getattr(usage, "estimated_cost_usd", 0.0) or 0.0)

        except Exception as exc:
            latency = (time.perf_counter() - started) * 1000
            error_code = str(getattr(exc, "code", type(exc).__name__))
            error_count += 1

        sr = rank_of(case["target"], preds, False)
        nr = rank_of(case["target"], preds, True)

        strict_ranks.append(sr)
        norm_ranks.append(nr)
        latencies.append(latency)
        costs.append(cost)

        if fallback not in ("none", "None", ""):
            fallback_count += 1

        rows.append(
            {
                "id": case["id"],
                "category": case.get("category", ""),
                "target": case["target"],
                "bci_input": case["bci_input"],
                "partner": case["partner"],
                "situation": case["situation"],
                "pred_1": preds[0] if len(preds) > 0 else "",
                "pred_2": preds[1] if len(preds) > 1 else "",
                "pred_3": preds[2] if len(preds) > 2 else "",
                "strict_rank": sr or "",
                "normalized_rank": nr or "",
                "latency_ms": round(latency, 2),
                "fallback": fallback,
                "estimated_cost_usd": cost,
                "service_error_code": error_code,
                "label": label,
            }
        )

        print(
            f"[{i:03d}/{len(cases):03d}] {case['bci_input']} "
            f"target={case['target']} preds={preds} strict={sr} norm={nr} "
            f"latency={int(latency)}ms error={error_code or '-'}"
        )

    n = len(cases)

    def acc1(rs):
        return sum(r == 1 for r in rs) / n

    def acc3(rs):
        return sum(r is not None and r <= 3 for r in rs) / n

    def mrr(rs):
        return sum(0 if r is None else 1 / r for r in rs) / n

    summary = {
        "label": label,
        "dataset": str(dataset),
        "n": n,
        "strict_acc_at_1": acc1(strict_ranks),
        "strict_acc_at_3": acc3(strict_ranks),
        "strict_mrr": mrr(strict_ranks),
        "normalized_acc_at_1": acc1(norm_ranks),
        "normalized_acc_at_3": acc3(norm_ranks),
        "normalized_mrr": mrr(norm_ranks),
        "mean_latency_ms": statistics.mean(latencies),
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "total_estimated_cost_usd": sum(costs),
        "mean_estimated_cost_usd": statistics.mean(costs) if costs else 0.0,
        "fallback_rate": fallback_count / n,
        "service_error_rate": error_count / n,
    }

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n=== TEST SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("CSV:", csv_path)
    print("Summary:", summary_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="eval/datasets/test_v1_150.jsonl")
    ap.add_argument("--label", default="manual")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    evaluate(Path(args.dataset), args.label, args.limit)


if __name__ == "__main__":
    main()
