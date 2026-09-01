from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from training_v2.common import extract_initials, normalize_text


REVIEW = Path("training_v2/reviews/teacher_candidate_review.csv")
CHECKPOINT = Path("training_v2/artifacts/teacher_checkpoint.json")
OUTPUT = Path("training_v2/artifacts/post_teacher_summary.json")

EXPECTED_GROUPS = 234


def truthy(value) -> bool:
    return str(value or "").strip().lower() in {
        "1", "true", "yes", "y", "approved", "ok"
    }


def main() -> int:
    if not REVIEW.exists():
        print(f"ERROR: {REVIEW} 파일이 없습니다.")
        return 1

    with REVIEW.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:
        rows = list(csv.DictReader(f))

    checkpoint_done = None
    checkpoint_errors = {}

    if CHECKPOINT.exists():
        payload = json.loads(
            CHECKPOINT.read_text(encoding="utf-8")
        )

        checkpoint_done = len(
            payload.get("done", {})
        )

        checkpoint_errors = (
            payload.get("errors", {}) or {}
        )

    mismatch = []
    duplicates = []

    seen = set()

    approved_rows = []
    teacher_rows = []
    curated_rows = []

    for line_no, row in enumerate(rows, start=2):

        initials = str(
            row.get("initials") or ""
        ).strip()

        text = str(
            row.get("text") or ""
        ).strip()

        source = str(
            row.get("source") or ""
        ).strip()

        approved = truthy(
            row.get("approved")
        )

        if text and initials:

            extracted = extract_initials(text)

            if extracted != initials:

                mismatch.append(
                    {
                        "line": line_no,
                        "initials": initials,
                        "text": text,
                        "extracted": extracted,
                    }
                )

        key = (
            initials,
            normalize_text(text)
        )

        if key in seen:

            duplicates.append(
                {
                    "line": line_no,
                    "initials": initials,
                    "text": text,
                }
            )

        else:

            seen.add(key)

        if approved:
            approved_rows.append(row)

        if source == "teacher_generator":
            teacher_rows.append(row)

        else:
            curated_rows.append(row)

    approved_by_initials = defaultdict(list)

    for row in approved_rows:

        initials = str(
            row.get("initials") or ""
        ).strip()

        approved_by_initials[
            initials
        ].append(row)

    sizes = [
        len(v)
        for v
        in approved_by_initials.values()
    ]

    source_counts = Counter(
        str(r.get("source") or "")
        for r in approved_rows
    )

    category_counts = Counter(
        str(r.get("category") or "")
        for r in approved_rows
    )

    summary = {
        "rows_total": len(rows),

        "teacher_rows_total":
            len(teacher_rows),

        "curated_rows_total":
            len(curated_rows),

        "approved_rows_total":
            len(approved_rows),

        "approved_initial_groups":
            len(approved_by_initials),

        "approved_groups_ge_2":
            sum(x >= 2 for x in sizes),

        "approved_groups_ge_3":
            sum(x >= 3 for x in sizes),

        "approved_groups_ge_5":
            sum(x >= 5 for x in sizes),

        "approved_groups_ge_8":
            sum(x >= 8 for x in sizes),

        "approved_singletons":
            sum(x == 1 for x in sizes),

        "approved_source_counts":
            dict(source_counts),

        "approved_category_counts":
            dict(category_counts),

        "initial_mismatch_count":
            len(mismatch),

        "duplicate_count":
            len(duplicates),

        "checkpoint_done_groups":
            checkpoint_done,

        "checkpoint_error_groups":
            len(checkpoint_errors),

        "expected_groups":
            EXPECTED_GROUPS,
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 70)
    print("POST TEACHER REPORT")
    print("=" * 70)

    for k, v in summary.items():
        print(f"{k:30} : {v}")

    if checkpoint_done is not None:

        if checkpoint_done < EXPECTED_GROUPS:

            print()
            print(
                f"아직 완료되지 않음: "
                f"{checkpoint_done}/{EXPECTED_GROUPS}"
            )

            return 2

    if mismatch:

        print()
        print("초성 불일치 발견")

        for row in mismatch[:20]:
            print(row)

        return 3

    print()
    print("Teacher augmentation 완료.")
    print(
        "teacher_generator 후보를 "
        "사람이 검수하세요."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())