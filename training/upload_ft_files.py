from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from training_v2.common import load_dotenv_if_available


def main() -> None:
    load_dotenv_if_available()
    p = argparse.ArgumentParser()
    p.add_argument("--train", default="training_v2/data/openai/train_sft_v2.jsonl")
    p.add_argument("--dev", default="training_v2/data/openai/dev_sft_v2.jsonl")
    args = p.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY가 없습니다.")

    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    with Path(args.train).open("rb") as f:
        train_obj = client.files.create(file=f, purpose="fine-tune")
    with Path(args.dev).open("rb") as f:
        dev_obj = client.files.create(file=f, purpose="fine-tune")

    state = {
        "training_file_id": train_obj.id,
        "validation_file_id": dev_obj.id,
        "train_path": args.train,
        "dev_path": args.dev,
    }
    path = Path("training_v2/artifacts/uploaded_files_v2.json")
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(state, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
