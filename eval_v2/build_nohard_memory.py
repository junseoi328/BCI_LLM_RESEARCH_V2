from __future__ import annotations

import json
from pathlib import Path

from training_v2.common import normalize_text


INPUT_MEMORY = Path(
    "research/phrase_memory/"
    "approved_bci_phrase_bank_v2.jsonl"
)

HARD = Path(
    "training_v2/data/"
    "hard50_v2.jsonl"
)

OUTPUT_MEMORY = Path(
    "research/phrase_memory/"
    "approved_bci_phrase_bank_v2_nohard.jsonl"
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

    memory_rows = read_jsonl(
        INPUT_MEMORY
    )

    hard_rows = read_jsonl(
        HARD
    )

    hard_targets = {

        (
            row["bci_input"],
            normalize_text(
                row["target"]
            ),
        )

        for row in hard_rows
    }

    kept = []
    removed = []

    for row in memory_rows:

        key = (
            row["initials"],
            normalize_text(
                row["text"]
            ),
        )

        if key in hard_targets:

            removed.append(row)

        else:

            kept.append(row)

    OUTPUT_MEMORY.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_MEMORY.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as f:

        for row in kept:

            f.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
                + "\n"
            )

    print("=" * 70)
    print("NO-HARD MEMORY CREATED")
    print("=" * 70)

    print(
        "Original :",
        len(memory_rows)
    )

    print(
        "Removed  :",
        len(removed)
    )

    print(
        "Remaining:",
        len(kept)
    )

    print(
        "Output   :",
        OUTPUT_MEMORY
    )

    print()

    print("REMOVED TARGETS")

    for row in removed:

        print(
            row["initials"],
            row["text"]
        )


if __name__ == "__main__":
    main()