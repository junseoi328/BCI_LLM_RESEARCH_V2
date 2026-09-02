from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from training_v2.common import load_dotenv_if_available

SUPPORTED = {
    "gpt-4.1-2025-04-14",
    "gpt-4.1-mini-2025-04-14",
    "gpt-4o-2024-08-06",
    "gpt-4o-mini-2024-07-18",
}


def auto_or_num(value: str):
    if value.strip().lower() == "auto":
        return "auto"
    if "." in value:
        return float(value)
    return int(value)


def main() -> None:
    load_dotenv_if_available()
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="gpt-4.1-mini-2025-04-14")
    p.add_argument("--suffix", default="bci-generator-v7-v2")
    p.add_argument("--epochs", default="auto")
    p.add_argument("--batch-size", default="auto")
    p.add_argument("--lr-multiplier", default="auto")
    args = p.parse_args()

    if args.model not in SUPPORTED:
        raise SystemExit(
            f"지원 확인이 필요한 model={args.model}. "
            "2026-09 기준 package 기본 지원 목록은 GPT-4.1/4.1-mini/4o/4o-mini snapshot입니다."
        )

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY가 없습니다.")

    state = json.loads(
        Path("training_v2/artifacts/uploaded_files_v2.json").read_text(encoding="utf-8")
    )

    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    job = client.fine_tuning.jobs.create(
        training_file=state["training_file_id"],
        validation_file=state["validation_file_id"],
        model=args.model,
        suffix=args.suffix,
        method={
            "type": "supervised",
            "supervised": {
                "hyperparameters": {
                    "n_epochs": auto_or_num(args.epochs),
                    "batch_size": auto_or_num(args.batch_size),
                    "learning_rate_multiplier": auto_or_num(args.lr_multiplier),
                }
            },
        },
        metadata={
            "project": "korean-bci-speller",
            "component": "candidate-generator",
            "dataset": "v2",
        },
    )

    out = {
        "job_id": job.id,
        "status": job.status,
        "base_model": args.model,
        "fine_tuned_model": getattr(job, "fine_tuned_model", None),
    }
    Path("training_v2/artifacts/ft_job_v2.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("Dashboard: https://platform.openai.com/finetune")


if __name__ == "__main__":
    main()
