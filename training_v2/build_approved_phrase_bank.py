from __future__ import annotations

import csv
import json
from pathlib import Path

from training_v2.common import (
    extract_initials,
    normalize_text,
)


INPUT = Path(
    "training_v2/reviews/"
    "teacher_candidate_review.csv"
)

OUTPUT = Path(
    "research/phrase_memory/"
    "approved_bci_phrase_bank_v2.jsonl"
)


def is_approved(value) -> bool:
    return (
        str(value or "")
        .strip()
        .lower()
        in {
            "1",
            "true",
            "yes",
            "y",
            "approved",
            "ok",
        }
    )


def main() -> int:

    if not INPUT.exists():

        print(
            "ERROR:",
            INPUT,
            "파일이 없습니다."
        )

        return 1

    with INPUT.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        rows = list(
            csv.DictReader(f)
        )

    seen = set()
    output = []

    for row in rows:

        if not is_approved(
            row.get("approved")
        ):
            continue

        text = str(
            row.get("text") or ""
        ).strip()

        initials = str(
            row.get("initials") or ""
        ).strip()

        if not text or not initials:
            continue

        extracted = (
            extract_initials(text)
        )

        if extracted != initials:

            print(
                "SKIP initials mismatch:",
                initials,
                text,
                extracted,
            )

            continue

        key = (
            initials,
            normalize_text(text),
        )

        if key in seen:
            continue

        seen.add(key)

        source = str(
            row.get("source") or ""
        ).strip()

        category = str(
            row.get("category") or ""
        ).strip()

        # 사람이 만든 seed를 조금 더 강하게,
        # teacher 승인 후보는 약간 낮게 시작.
        if source == "curated_seed_v2":
            weight = 1.0
        else:
            weight = 0.85

        output.append(
            {
                "initials": initials,
                "text": text,
                "category": category,
                "source": source,
                "weight": weight,
            }
        )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as f:

        for row in output:

            f.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
                + "\n"
            )

    print("=" * 70)

    print(
        "APPROVED PHRASES:",
        len(output)
    )

    print(
        "OUTPUT:",
        OUTPUT
    )

    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())