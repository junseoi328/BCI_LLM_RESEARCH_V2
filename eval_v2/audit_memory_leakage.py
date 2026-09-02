from __future__ import annotations

import json
from pathlib import Path

from training_v2.common import normalize_text


MEMORY = Path(
    "research/phrase_memory/"
    "approved_bci_phrase_bank_v2.jsonl"
)

HARD = Path(
    "training_v2/data/"
    "hard50_v2.jsonl"
)


def read_jsonl(path: Path):
    rows = []

    with path.open(
        "r",
        encoding="utf-8-sig",
    ) as f:

        for line in f:

            line = line.strip()

            if line:
                rows.append(
                    json.loads(line)
                )

    return rows


def main():

    memory_rows = read_jsonl(MEMORY)
    hard_rows = read_jsonl(HARD)

    memory_map = {}

    for row in memory_rows:

        key = (
            row["initials"],
            normalize_text(
                row["text"]
            ),
        )

        memory_map[key] = row

    leaked = []

    for row in hard_rows:

        key = (
            row["bci_input"],
            normalize_text(
                row["target"]
            ),
        )

        if key in memory_map:

            leaked.append(
                {
                    "id":
                        row["id"],

                    "initials":
                        row["bci_input"],

                    "target":
                        row["target"],
                }
            )

    print("=" * 70)
    print("MEMORY LEAKAGE AUDIT")
    print("=" * 70)

    print(
        "Memory phrases :",
        len(memory_rows)
    )

    print(
        "HARD cases     :",
        len(hard_rows)
    )

    print(
        "Exact overlap  :",
        len(leaked)
    )

    print(
        "Leakage rate   :",
        len(leaked)
        /
        len(hard_rows)
        if hard_rows
        else 0
    )

    print()

    for row in leaked:

        print(
            row["id"],
            row["initials"],
            row["target"]
        )


if __name__ == "__main__":
    main()