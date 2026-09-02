from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path

from training.common import extract_initials, normalize_text, read_jsonl

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def load_model(state_path: str) -> str:
    payload = json.loads(Path(state_path).read_text(encoding="utf-8"))
    model = payload.get("fine_tuned_model")
    if not model:
        raise SystemExit("fine_tuned_model이 없습니다.")
    return model


def evaluate_model(model: str, dataset_path: str, count: int = 16) -> dict:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY가 없습니다.")

    from app.llm.prompts import GENERATOR_INSTRUCTIONS, build_generator_input
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=60.0, max_retries=2)
    rows = read_jsonl(dataset_path)

    schema = {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": count,
            }
        },
        "required": ["candidates"],
        "additionalProperties": False,
    }

    recalls = []
    any_hits = 0
    valid_rates = []
    latencies = []

    # 같은 initials가 반복되는 80 validation examples라 API 비용을 줄이기 위해 group별 1회만 호출.
    by_initials: dict[str, set[str]] = {}
    for row in rows:
        by_initials.setdefault(row["initials"], set()).update(row["candidates"])

    detail = []
    for initials, gold_set in by_initials.items():
        t0 = time.perf_counter()
        response = client.responses.create(
            model=model,
            instructions=GENERATOR_INSTRUCTIONS,
            input=build_generator_input(initials, count),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "bci_candidate_generation",
                    "strict": True,
                    "schema": schema,
                },
            },
            store=False,
        )
        latency = int((time.perf_counter() - t0) * 1000)
        latencies.append(latency)

        data = json.loads(response.output_text)
        preds = [str(x).strip() for x in data.get("candidates", []) if str(x).strip()]
        pred_norm = {normalize_text(x) for x in preds}
        gold_norm = {normalize_text(x) for x in gold_set}

        hits = len(pred_norm & gold_norm)
        recall = hits / len(gold_norm) if gold_norm else 0.0
        recalls.append(recall)
        any_hits += hits > 0

        valid = sum(extract_initials(x) == initials for x in preds)
        valid_rate = valid / len(preds) if preds else 0.0
        valid_rates.append(valid_rate)

        detail.append(
            {
                "initials": initials,
                "gold": sorted(gold_set),
                "preds": preds,
                "gold_recall": recall,
                "valid_initial_rate": valid_rate,
                "latency_ms": latency,
            }
        )
        print(
            f"{initials} recall={recall:.3f} valid={valid_rate:.3f} "
            f"latency={latency}ms preds={preds}"
        )

    summary = {
        "model": model,
        "dataset": dataset_path,
        "groups": len(by_initials),
        "mean_gold_recall": statistics.mean(recalls) if recalls else 0.0,
        "any_gold_hit_rate": any_hits / len(by_initials) if by_initials else 0.0,
        "mean_valid_initial_rate": statistics.mean(valid_rates) if valid_rates else 0.0,
        "mean_latency_ms": statistics.mean(latencies) if latencies else 0.0,
        "detail": detail,
    }
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model-state", default="training/artifacts/ft_model.json")
    p.add_argument("--dataset", default="training/data/dev_semantic_v1.jsonl")
    p.add_argument("--output", default="training/artifacts/ft_dev_coverage.json")
    args = p.parse_args()

    ft_model = load_model(args.model_state)
    ft = evaluate_model(ft_model, args.dataset)
    Path(args.output).write_text(json.dumps(ft, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nSUMMARY")
    print(json.dumps({k:v for k,v in ft.items() if k != "detail"}, ensure_ascii=False, indent=2))
    print("OUTPUT:", args.output)


if __name__ == "__main__":
    main()
