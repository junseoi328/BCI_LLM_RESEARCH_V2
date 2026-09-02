from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


TRAIN = Path(
    "training_v2/data/openai/"
    "train_sft_v2.jsonl"
)

DEV = Path(
    "training_v2/data/openai/"
    "dev_sft_v2.jsonl"
)

STATE = Path(
    "training_v2/artifacts/"
    "uploaded_files_v2.json"
)


def main():

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY 없음"
        )

    client = OpenAI(
        api_key=api_key
    )

    print("Uploading TRAIN...")

    with TRAIN.open("rb") as f:

        train_file = (
            client.files.create(
                file=f,
                purpose="fine-tune",
            )
        )

    print(
        "TRAIN FILE ID:",
        train_file.id
    )

    print("Uploading DEV...")

    with DEV.open("rb") as f:

        dev_file = (
            client.files.create(
                file=f,
                purpose="fine-tune",
            )
        )

    print(
        "DEV FILE ID:",
        dev_file.id
    )

    state = {
        "training_file_id":
            train_file.id,

        "validation_file_id":
            dev_file.id,
    }

    STATE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    STATE.write_text(
        json.dumps(
            state,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("SAVED:", STATE)


if __name__ == "__main__":
    main()