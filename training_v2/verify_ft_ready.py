from __future__ import annotations

import json
from pathlib import Path

from training_v2.common import (
    extract_initials,
    normalize_text,
    read_jsonl,
)


TRAIN = Path(
    "training_v2/data/train_semantic_v2.jsonl"
)

DEV = Path(
    "training_v2/data/dev_semantic_v2.jsonl"
)

HARD = Path(
    "training_v2/data/hard50_v2.jsonl"
)

TRAIN_SFT = Path(
    "training_v2/data/openai/train_sft_v2.jsonl"
)

DEV_SFT = Path(
    "training_v2/data/openai/dev_sft_v2.jsonl"
)


def validate_semantic(
    path: Path
) -> list[str]:

    errors = []

    rows = read_jsonl(path)

    ids = set()

    for row in rows:

        rid = str(
            row.get("id") or ""
        )

        initials = str(
            row.get("initials") or ""
        )

        candidates = list(
            row.get("candidates") or []
        )

        target = str(
            row.get("target") or ""
        )

        if rid in ids:
            errors.append(
                f"{rid}: duplicate id"
            )

        ids.add(rid)

        if not initials:

            errors.append(
                f"{rid}: initials empty"
            )

        if not candidates:

            errors.append(
                f"{rid}: candidates empty"
            )

            continue

        seen = set()

        for text in candidates:

            text = str(text)

            extracted = (
                extract_initials(text)
            )

            if extracted != initials:

                errors.append(
                    f"{rid}: "
                    f"{text!r} -> {extracted}, "
                    f"expected={initials}"
                )

            key = normalize_text(text)

            if key in seen:

                errors.append(
                    f"{rid}: duplicate "
                    f"{text!r}"
                )

            seen.add(key)

        if target:

            candidate_norms = {
                normalize_text(str(x))
                for x in candidates
            }

            if (
                normalize_text(target)
                not in candidate_norms
            ):

                errors.append(
                    f"{rid}: "
                    "target not in candidates"
                )

        requested = int(
            row.get(
                "requested_count",
                len(candidates)
            )
        )

        if requested < len(candidates):

            errors.append(
                f"{rid}: "
                f"requested={requested}, "
                f"candidates={len(candidates)}"
            )

    return errors


def validate_sft(
    path: Path
) -> list[str]:

    errors = []

    with path.open(
        "r",
        encoding="utf-8-sig"
    ) as f:

        for line_no, line in enumerate(
            f,
            start=1,
        ):

            try:

                row = json.loads(line)

                messages = row["messages"]

                roles = [
                    x["role"]
                    for x in messages
                ]

                if roles != [
                    "system",
                    "user",
                    "assistant",
                ]:

                    errors.append(
                        f"{line_no}: "
                        f"roles={roles}"
                    )

                    continue

                assistant = json.loads(
                    messages[-1]["content"]
                )

                candidates = (
                    assistant["candidates"]
                )

                if (
                    not isinstance(
                        candidates,
                        list
                    )
                    or not candidates
                ):

                    errors.append(
                        f"{line_no}: "
                        "empty candidates"
                    )

            except Exception as exc:

                errors.append(
                    f"{line_no}: {exc}"
                )

    return errors


def main() -> int:

    required = [
        TRAIN,
        DEV,
        HARD,
        TRAIN_SFT,
        DEV_SFT,
    ]

    missing = [
        str(x)
        for x in required
        if not x.exists()
    ]

    if missing:

        print("MISSING FILES")

        for x in missing:
            print(x)

        return 1

    train = read_jsonl(TRAIN)
    dev = read_jsonl(DEV)
    hard = read_jsonl(HARD)

    errors = []

    errors += validate_semantic(TRAIN)
    errors += validate_semantic(DEV)

    errors += validate_sft(TRAIN_SFT)
    errors += validate_sft(DEV_SFT)

    train_groups = {
        x["initials"]
        for x in train
    }

    dev_groups = {
        x["initials"]
        for x in dev
    }

    overlap = sorted(
        train_groups & dev_groups
    )

    if overlap:

        errors.append(
            "TRAIN/DEV group leakage: "
            + str(overlap[:20])
        )

    for row in hard:

        target = str(
            row["target"]
        )

        initials = str(
            row["bci_input"]
        )

        if (
            extract_initials(target)
            != initials
        ):

            errors.append(
                f"{row['id']}: "
                "HARD initials mismatch"
            )

    print("=" * 70)
    print("FINE-TUNING READY CHECK")
    print("=" * 70)

    print(
        "TRAIN examples:",
        len(train)
    )

    print(
        "DEV examples:",
        len(dev)
    )

    print(
        "HARD examples:",
        len(hard)
    )

    print(
        "TRAIN groups:",
        len(train_groups)
    )

    print(
        "DEV groups:",
        len(dev_groups)
    )

    print(
        "TRAIN/DEV overlap:",
        len(overlap)
    )

    print(
        "Errors:",
        len(errors)
    )

    for error in errors[:100]:
        print("ERROR:", error)

    if errors:
        return 2

    print()
    print("READY FOR FINE-TUNING")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())