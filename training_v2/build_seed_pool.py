from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from training_v2.common import extract_initials, normalize_text, write_jsonl
from training_v2.seed_inventory import SEED_BLOCKS


def load_benchmark_targets(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    targets: set[str] = set()
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            target = row.get("target")
            if target:
                targets.add(normalize_text(str(target)))
    return targets


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=20260901)
    p.add_argument("--dev-group-ratio", type=float, default=0.25)
    p.add_argument("--benchmark", default="eval/datasets/test_v1_150.jsonl")
    p.add_argument(
        "--allow-benchmark-overlap",
        action="store_true",
        help="기존 benchmark 표현을 hard-case mining용으로 허용. 이 경우 benchmark_v1은 더 이상 공정한 TEST가 아니다.",
    )
    args = p.parse_args()

    rows: list[dict] = []
    seen: set[str] = set()
    for block in SEED_BLOCKS:
        for phrase in block["phrases"]:
            phrase = str(phrase).strip()
            key = normalize_text(phrase)
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "phrase_id": f"P{len(rows)+1:04d}",
                    "category": block["category"],
                    "text": phrase,
                    "initials": extract_initials(phrase),
                    "partner": block["partner"],
                    "situation": block["situation"],
                    "recent_context": [block["context"]],
                    "source": "curated_seed_v2",
                    "approved": 1,
                    "note": "",
                }
            )

    benchmark_path = Path(args.benchmark)
    benchmark_targets = load_benchmark_targets(benchmark_path)
    excluded = []
    if benchmark_targets and not args.allow_benchmark_overlap:
        kept = []
        for row in rows:
            if normalize_text(row["text"]) in benchmark_targets:
                excluded.append(row)
            else:
                kept.append(row)
        rows = kept

    by_initials: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_initials[row["initials"]].append(row)

    rng = random.Random(args.seed)
    groups = list(by_initials)
    rng.shuffle(groups)

    # initial-group split. 같은 초성 그룹은 TRAIN/DEV에 동시에 들어가지 않는다.
    n_dev = max(20, int(round(len(groups) * args.dev_group_ratio)))
    dev_groups = set(groups[:n_dev])

    train_rows = []
    dev_rows = []
    for initials, items in by_initials.items():
        split = "dev" if initials in dev_groups else "train"
        for row in items:
            out = dict(row)
            out["split"] = split
            (dev_rows if split == "dev" else train_rows).append(out)

    out_dir = Path("training_v2/data")
    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "seed_train_pool.jsonl", train_rows)
    write_jsonl(out_dir / "seed_dev_pool.jsonl", dev_rows)
    write_jsonl(out_dir / "seed_all_pool.jsonl", train_rows + dev_rows)

    review_path = Path("training_v2/reviews/candidate_pool_review_v2.csv")
    review_path.parent.mkdir(parents=True, exist_ok=True)
    with review_path.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "phrase_id","split","category","initials","text","partner",
            "situation","recent_context","source","approved","priority","note",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in train_rows + dev_rows:
            w.writerow(
                {
                    **{k: row.get(k, "") for k in fieldnames},
                    "recent_context": " | ".join(row.get("recent_context", [])),
                    "priority": "high" if row["category"] in {
                        "medical_communication","pain_discomfort","positioning","ambiguity"
                    } else "normal",
                }
            )

    stats = {
        "seed_phrases_before_benchmark_exclusion": len(seen),
        "benchmark_excluded": len(excluded),
        "usable_phrases": len(train_rows) + len(dev_rows),
        "train_phrases": len(train_rows),
        "dev_phrases": len(dev_rows),
        "unique_initial_groups": len(groups),
        "train_initial_groups": len(set(r["initials"] for r in train_rows)),
        "dev_initial_groups": len(set(r["initials"] for r in dev_rows)),
        "category_counts": dict(Counter(r["category"] for r in train_rows + dev_rows)),
        "review_csv": str(review_path),
    }
    Path("training_v2/artifacts/seed_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print("REVIEW:", review_path)
    if excluded:
        print(f"기존 benchmark exact overlap {len(excluded)}개를 TRAIN/DEV에서 제외했습니다.")


if __name__ == "__main__":
    main()
