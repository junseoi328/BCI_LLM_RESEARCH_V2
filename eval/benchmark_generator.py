from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from collections import defaultdict
from pathlib import Path

from training_v2.common import extract_initials, load_dotenv_if_available, normalize_text, read_jsonl


def collect_gold(path: str) -> dict[str, set[str]]:
    by: dict[str, set[str]] = defaultdict(set)
    for row in read_jsonl(path):
        by[row["initials"]].update(row["candidates"])
    return by


def run_model(model: str, gold: dict[str, set[str]], count: int) -> dict:
    from app.llm.prompts import GENERATOR_INSTRUCTIONS, build_generator_input
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=60.0, max_retries=2)
    schema = {
        "type":"object",
        "properties":{
            "candidates":{"type":"array","items":{"type":"string"}}
        },
        "required":["candidates"],
        "additionalProperties":False,
    }

    rows = []
    for initials, expected in sorted(gold.items()):
        t0 = time.perf_counter()
        response = client.responses.create(
            model=model,
            instructions=GENERATOR_INSTRUCTIONS,
            input=build_generator_input(initials, count),
            max_output_tokens=1600,
            text={
                "format":{
                    "type":"json_schema",
                    "name":"bci_candidate_generation",
                    "strict":True,
                    "schema":schema,
                }
            },
            store=False,
        )
        latency = int((time.perf_counter() - t0) * 1000)
        payload = json.loads(response.output_text)
        preds = [str(x).strip() for x in payload.get("candidates", []) if str(x).strip()]

        pred_norm = {normalize_text(x) for x in preds}
        gold_norm = {normalize_text(x) for x in expected}
        hits = len(pred_norm & gold_norm)
        valid = sum(extract_initials(x) == initials for x in preds)

        row = {
            "initials": initials,
            "gold_count": len(gold_norm),
            "pred_count": len(preds),
            "gold_recall": hits / len(gold_norm) if gold_norm else 0.0,
            "any_gold_hit": hits > 0,
            "initial_valid_rate": valid / len(preds) if preds else 0.0,
            "latency_ms": latency,
            "preds": preds,
        }
        rows.append(row)
        print(
            f"{initials} recall={row['gold_recall']:.3f} "
            f"valid={row['initial_valid_rate']:.3f} latency={latency}ms"
        )

    return {
        "model": model,
        "groups": len(rows),
        "mean_gold_recall": statistics.mean(x["gold_recall"] for x in rows) if rows else 0,
        "any_gold_hit_rate": statistics.mean(float(x["any_gold_hit"]) for x in rows) if rows else 0,
        "mean_initial_valid_rate": statistics.mean(x["initial_valid_rate"] for x in rows) if rows else 0,
        "mean_latency_ms": statistics.mean(x["latency_ms"] for x in rows) if rows else 0,
        "rows": rows,
    }


def main() -> None:
    load_dotenv_if_available()
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="training_v2/data/dev_semantic_v2.jsonl")
    p.add_argument("--base-model", default="gpt-5.6-luna")
    p.add_argument("--ft-state", default="training_v2/artifacts/ft_model_v2.json")
    p.add_argument("--count", type=int, default=16)
    args = p.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY 없음")

    state = json.loads(Path(args.ft_state).read_text(encoding="utf-8"))
    ft_model = state["fine_tuned_model"]
    gold = collect_gold(args.dataset)

    print("\n=== BASE ===")
    base = run_model(args.base_model, gold, args.count)
    print("\n=== FINE-TUNED ===")
    ft = run_model(ft_model, gold, args.count)

    summary = {
        "base": {k:v for k,v in base.items() if k != "rows"},
        "fine_tuned": {k:v for k,v in ft.items() if k != "rows"},
        "delta": {
            "mean_gold_recall": ft["mean_gold_recall"] - base["mean_gold_recall"],
            "any_gold_hit_rate": ft["any_gold_hit_rate"] - base["any_gold_hit_rate"],
            "mean_initial_valid_rate": ft["mean_initial_valid_rate"] - base["mean_initial_valid_rate"],
            "mean_latency_ms": ft["mean_latency_ms"] - base["mean_latency_ms"],
        },
    }
    Path("eval_v2/reports/generator_v7_v2_comparison.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
