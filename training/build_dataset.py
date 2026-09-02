from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

from training.catalog import TRAIN_GROUPS, DEV_GROUPS
from training.common import extract_initials, unique_preserve, write_jsonl


COUNTS = [3, 5, 8, 12, 16]


def _validate_groups(groups: dict[str, list[str]]) -> None:
    for initials, candidates in groups.items():
        if len(candidates) < 2:
            raise RuntimeError(f"{initials}: 후보가 최소 2개 필요합니다.")
        for text in candidates:
            got = extract_initials(text)
            if got != initials:
                raise RuntimeError(
                    f"초성 불일치: key={initials} text={text!r} extracted={got}"
                )


def _build_split(
    groups: dict[str, list[str]],
    n_examples: int,
    seed: int,
    split: str,
) -> list[dict]:
    rng = random.Random(seed)
    keys = list(groups)
    rows: list[dict] = []

    for i in range(n_examples):
        initials = keys[i % len(keys)]
        base = unique_preserve(groups[initials])
        desired_count = COUNTS[i % len(COUNTS)]

        # 같은 초성의 다양한 후보가 여러 순서로 노출되도록 회전 + shuffle.
        offset = (i // len(keys)) % len(base)
        rotated = base[offset:] + base[:offset]

        # 일부 예제는 전체 순서를 섞어 특정 후보 1개에 과적합되는 것을 줄임.
        if (i // len(keys)) % 3 == 2:
            shuffled = rotated[:]
            rng.shuffle(shuffled)
            rotated = shuffled

        out = rotated[: min(desired_count, len(rotated))]

        rows.append(
            {
                "id": f"{split.upper()}{i+1:04d}",
                "split": split,
                "initials": initials,
                "requested_count": desired_count,
                "candidates": out,
                "catalog_size": len(base),
            }
        )
    return rows


def _review_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "id", "split", "initials", "requested_count",
                "candidates", "approved", "note",
            ],
        )
        w.writeheader()
        for row in rows:
            w.writerow(
                {
                    "id": row["id"],
                    "split": row["split"],
                    "initials": row["initials"],
                    "requested_count": row["requested_count"],
                    "candidates": " | ".join(row["candidates"]),
                    "approved": 1,
                    "note": "",
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-n", type=int, default=500)
    parser.add_argument("--dev-n", type=int, default=80)
    parser.add_argument("--seed", type=int, default=20260901)
    parser.add_argument("--out-dir", default="training/data")
    args = parser.parse_args()

    _validate_groups(TRAIN_GROUPS)
    _validate_groups(DEV_GROUPS)

    overlap = set(TRAIN_GROUPS) & set(DEV_GROUPS)
    if overlap:
        raise RuntimeError(f"TRAIN/DEV initial-group leakage: {sorted(overlap)}")

    out_dir = Path(args.out_dir)
    train = _build_split(TRAIN_GROUPS, args.train_n, args.seed, "train")
    dev = _build_split(DEV_GROUPS, args.dev_n, args.seed + 1, "dev")

    write_jsonl(out_dir / "train_semantic_v1.jsonl", train)
    write_jsonl(out_dir / "dev_semantic_v1.jsonl", dev)
    _review_csv(out_dir / "train_review_v1.csv", train)
    _review_csv(out_dir / "dev_review_v1.csv", dev)

    print(f"TRAIN: {len(train)} -> {out_dir/'train_semantic_v1.jsonl'}")
    print(f"DEV  : {len(dev)} -> {out_dir/'dev_semantic_v1.jsonl'}")
    print("리뷰용 CSV도 함께 생성했습니다. 학습 전 부자연스러운 후보는 반드시 확인하세요.")


if __name__ == "__main__":
    main()
