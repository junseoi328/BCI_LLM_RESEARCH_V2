from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def latest_summary(label: str):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", label)
    files = sorted(Path("eval/reports").glob(f"test_v1_{safe}_*.summary.json"))
    return files[-1] if files else None


def run_one(label: str, env_overrides: dict[str, str], dataset: str, limit: int | None):
    env = os.environ.copy()
    env.update(env_overrides)

    cmd = [
        sys.executable,
        "-m",
        "eval.run_test_v1",
        "--dataset",
        dataset,
        "--label",
        label,
    ]
    if limit:
        cmd += ["--limit", str(limit)]

    print("\n" + "=" * 80)
    print("RUN", label)
    print("=" * 80)
    subprocess.run(cmd, env=env, check=True)
    return latest_summary(label)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="eval/datasets/test_v1_150.jsonl")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    common = {
        "MOCK_MODE": "false",
        "DEBUG_MODE": "false",
        "ALLOW_LOCAL_FALLBACK": "false",
        "OPENAI_GENERATOR_MODEL": "gpt-5.6-luna",
        "OPENAI_RANKER_MODEL": "gpt-5.6-luna",
        "GENERATION_COUNT": "16",
        "RANKER_PROMPT_VERSION": "ranker-v2",
    }

    baseline = {
        **common,
        "ENSEMBLE_MODE": "off",
        "GENERATOR_PROMPT_VERSION": "generator-v2",
        "PIPELINE_VERSION": "0.2.0-baseline-retest",
    }

    v63 = {
        **common,
        "ENSEMBLE_MODE": "context_quality",
        "DIVERSITY_GENERATION_COUNT": "8",
        "ENSEMBLE_MIN_VALID": "6",
        "ENSEMBLE_CONTEXT_THRESHOLD": "0.72",
        "ENSEMBLE_INTENT_THRESHOLD": "0.72",
        "GENERATOR_PROMPT_VERSION": "generator-v2+context-diversity-v2",
        "PIPELINE_VERSION": "0.4.3-context-quality-v6-3",
    }

    p1 = run_one("baseline_v2_retest", baseline, args.dataset, args.limit)
    p2 = run_one("v6_3_context_quality", v63, args.dataset, args.limit)

    if not (p1 and p2):
        print("Summary file not found.")
        return

    a = json.loads(p1.read_text(encoding="utf-8"))
    b = json.loads(p2.read_text(encoding="utf-8"))

    keys = [
        "strict_acc_at_1",
        "strict_acc_at_3",
        "normalized_acc_at_1",
        "normalized_acc_at_3",
        "normalized_mrr",
        "mean_latency_ms",
        "p95_latency_ms",
        "mean_estimated_cost_usd",
        "fallback_rate",
        "service_error_rate",
    ]

    print("\n" + "=" * 80)
    print("PAIR COMPARISON: v6.3 - baseline")
    print("=" * 80)

    for k in keys:
        av = a.get(k)
        bv = b.get(k)
        delta = (bv - av) if isinstance(av, (int, float)) and isinstance(bv, (int, float)) else None
        print(f"{k:30s} baseline={av}  v6.3={bv}  delta={delta}")


if __name__ == "__main__":
    main()
