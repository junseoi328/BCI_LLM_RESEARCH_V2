from __future__ import annotations

import argparse
import json
from pathlib import Path

from training_v2.common import extract_initials, normalize_text, read_jsonl


def validate_semantic(path: Path) -> list[str]:
    rows = read_jsonl(path)
    errors = []
    ids = set()
    for row in rows:
        rid = row.get("id")
        if rid in ids:
            errors.append(f"{rid}: duplicate id")
        ids.add(rid)

        initials = str(row.get("initials") or "")
        candidates = row.get("candidates") or []
        if not initials or not candidates:
            errors.append(f"{rid}: empty initials/candidates")
            continue

        seen = set()
        for text in candidates:
            if extract_initials(str(text)) != initials:
                errors.append(f"{rid}: initials mismatch {text!r}")
            key = normalize_text(str(text))
            if key in seen:
                errors.append(f"{rid}: duplicate candidate {text!r}")
            seen.add(key)

        target = str(row.get("target") or "")
        if target and normalize_text(target) not in {normalize_text(str(x)) for x in candidates}:
            errors.append(f"{rid}: target not in candidates")
    return errors


def validate_hard(path: Path) -> list[str]:
    errors = []
    for row in read_jsonl(path):
        if extract_initials(str(row["target"])) != str(row["bci_input"]):
            errors.append(f"{row['id']}: hard initials mismatch")
    return errors


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--train", default="training_v2/data/train_semantic_v2.jsonl")
    p.add_argument("--dev", default="training_v2/data/dev_semantic_v2.jsonl")
    p.add_argument("--hard", default="training_v2/data/hard50_v2.jsonl")
    args = p.parse_args()

    train = read_jsonl(args.train)
    dev = read_jsonl(args.dev)

    train_groups = {x["initials"] for x in train}
    dev_groups = {x["initials"] for x in dev}
    overlap = sorted(train_groups & dev_groups)

    errors = (
        validate_semantic(Path(args.train))
        + validate_semantic(Path(args.dev))
        + validate_hard(Path(args.hard))
    )
    if overlap:
        errors.append(f"TRAIN/DEV initials overlap: {overlap[:20]}")

    print(f"TRAIN={len(train)} DEV={len(dev)} HARD={len(read_jsonl(args.hard))}")
    print(f"TRAIN groups={len(train_groups)} DEV groups={len(dev_groups)}")
    print(f"ERRORS={len(errors)}")
    for err in errors[:100]:
        print("ERROR:", err)

    if errors:
        return 2
    print("DATASET V2 VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
