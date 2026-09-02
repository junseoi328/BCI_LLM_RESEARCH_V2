from __future__ import annotations

import argparse
import json
from pathlib import Path


METRICS = [
    "strict_acc_at_1",
    "strict_acc_at_3",
    "normalized_acc_at_1",
    "normalized_acc_at_3",
    "normalized_mrr",
    "mean_latency_ms",
    "p50_latency_ms",
    "p95_latency_ms",
    "total_estimated_cost_usd",
    "mean_estimated_cost_usd",
    "fallback_rate_successful_cases",
    "service_error_rate",
]


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", default=r"eval\reports\baseline_v2_reliable.summary.json")
    p.add_argument("--v63", default=r"eval\reports\v6_3_context_quality_reliable.summary.json")
    args = p.parse_args()

    a = load(args.baseline)
    b = load(args.v63)

    print("=" * 88)
    print("RELIABLE PAIR COMPARISON")
    print("=" * 88)
    print(f"baseline valid_for_reporting = {a.get('valid_for_reporting')}")
    print(f"v6.3     valid_for_reporting = {b.get('valid_for_reporting')}")
    print()

    if not a.get("valid_for_reporting") or not b.get("valid_for_reporting"):
        print("STOP: 두 run 모두 service_error_count=0 이어야 공식 비교가 가능합니다.")
        return 2

    for key in METRICS:
        av = a.get(key)
        bv = b.get(key)
        if isinstance(av, (int, float)) and isinstance(bv, (int, float)):
            delta = bv - av
        else:
            delta = None
        print(f"{key:<36} baseline={av!s:<18} v6.3={bv!s:<18} delta={delta}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
