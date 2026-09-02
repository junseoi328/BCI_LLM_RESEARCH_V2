from __future__ import annotations

import argparse
import json
from pathlib import Path

from training.catalog import TRAIN_GROUPS
from training.common import normalize_text


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="research/phrase_memory/common_phrase_bank.jsonl")
    args = p.parse_args()

    rows = []
    for initials, candidates in TRAIN_GROUPS.items():
        for rank, text in enumerate(candidates):
            rows.append(
                {
                    "initials": initials,
                    "text": text,
                    "weight": round(1.0 - min(rank, 8) * 0.05, 3),
                    "source": "train_catalog_v1",
                }
            )

    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"PHRASE BANK: {len(rows)} -> {path}")


if __name__ == "__main__":
    main()
