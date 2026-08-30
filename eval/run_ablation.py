from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.schemas import ContextLevel
from eval.run_eval import evaluate

ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(ROOT / "datasets" / "sanity_v1.jsonl"))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    dataset = Path(args.dataset)
    report = {}
    for level in ContextLevel:
        print(f"\n######## CONTEXT={level.value} ########")
        _, summary = evaluate(dataset, level, args.limit)
        report[level.value] = summary

    out = ROOT / "reports" / "context_ablation_latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== ABLATION ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
