from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(path: Path) -> list[str]:
    errors = []
    with path.open("r", encoding="utf-8-sig") as f:
        for i, line in enumerate(f, start=1):
            try:
                row = json.loads(line)
                msgs = row["messages"]
                if [x["role"] for x in msgs] != ["system","user","assistant"]:
                    errors.append(f"{i}: roles")
                    continue
                result = json.loads(msgs[-1]["content"])
                candidates = result["candidates"]
                if not isinstance(candidates, list) or not candidates:
                    errors.append(f"{i}: empty candidates")
            except Exception as exc:
                errors.append(f"{i}: {exc}")
    return errors


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "files",
        nargs="*",
        default=[
            "training_v2/data/openai/train_sft_v2.jsonl",
            "training_v2/data/openai/dev_sft_v2.jsonl",
        ],
    )
    args = p.parse_args()

    count = 0
    for name in args.files:
        errors = validate(Path(name))
        count += len(errors)
        print(f"{name}: errors={len(errors)}")
        for x in errors[:30]:
            print(" ", x)
    return 0 if count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
