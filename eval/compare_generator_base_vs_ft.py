from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.evaluate_ft_generator import evaluate_model

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model-state", default="training/artifacts/ft_model.json")
    p.add_argument("--base-model", default="gpt-5.6-luna")
    p.add_argument("--dataset", default="training/data/dev_semantic_v1.jsonl")
    p.add_argument("--output", default="training/artifacts/generator_comparison.json")
    args = p.parse_args()

    state = json.loads(Path(args.model_state).read_text(encoding="utf-8"))
    ft_model = state["fine_tuned_model"]

    print("\n=== BASE GENERATOR ===")
    base = evaluate_model(args.base_model, args.dataset)

    print("\n=== FINE-TUNED GENERATOR ===")
    ft = evaluate_model(ft_model, args.dataset)

    keys = [
        "mean_gold_recall",
        "any_gold_hit_rate",
        "mean_valid_initial_rate",
        "mean_latency_ms",
    ]
    comparison = {
        "base_model": args.base_model,
        "fine_tuned_model": ft_model,
        "metrics": {
            k: {
                "base": base[k],
                "fine_tuned": ft[k],
                "delta": ft[k] - base[k],
            }
            for k in keys
        },
    }
    Path(args.output).write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("\n=== COMPARISON ===")
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
