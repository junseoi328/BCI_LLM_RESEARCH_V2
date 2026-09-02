from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from training_v2.common import extract_initials, normalize_text, write_jsonl
from training_v2.review_io import approved, load_review


COUNTS = [4, 6, 8, 12, 16]


def group_rows(rows: list[dict]) -> dict[str, list[dict]]:
    by: dict[str, list[dict]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()

    for row in rows:
        if not approved(row.get("approved")):
            continue
        text = str(row.get("text") or "").strip()
        initials = str(row.get("initials") or "").strip()
        if not text or not initials:
            continue
        if extract_initials(text) != initials:
            continue
        key = (initials, normalize_text(text))
        if key in seen:
            continue
        seen.add(key)
        by[initials].append(
            {
                "text": text,
                "category": str(row.get("category") or "other"),
                "split": str(row.get("split") or "train"),
                "source": str(row.get("source") or "review"),
            }
        )
    return by


def build_examples(
    groups: dict[str, list[dict]],
    split: str,
    n: int,
    seed: int,
) -> list[dict]:
    rng = random.Random(seed)

    # 후보를 category별로 펼친다. 같은 initials group은 이미 split이 분리되어 있다.
    category_items: dict[str, list[tuple[str, dict, list[dict]]]] = defaultdict(list)
    for initials, items in groups.items():
        split_items = [x for x in items if x["split"] == split]
        for item in split_items:
            category_items[item["category"]].append((initials, item, split_items))

    if not category_items:
        raise RuntimeError(f"{split} candidate 없음")

    # TRAIN은 BCI 핵심군과 ambiguity를 조금 더 많이, 나머지는 균형 배치.
    train_weights = {
        "basic_request": 40,
        "food_drink": 40,
        "environment": 40,
        "positioning": 60,
        "pain_discomfort": 60,
        "medical_communication": 60,
        "schedule_time": 35,
        "social": 35,
        "questions_answers": 35,
        "emotion_needs": 35,
        "communication_control": 40,
        "device_control": 40,
        "ambiguity": 80,
    }
    dev_weights = {
        "basic_request": 7,
        "food_drink": 7,
        "environment": 7,
        "positioning": 10,
        "pain_discomfort": 10,
        "medical_communication": 10,
        "schedule_time": 6,
        "social": 6,
        "questions_answers": 6,
        "emotion_needs": 6,
        "communication_control": 6,
        "device_control": 6,
        "ambiguity": 13,
    }

    desired = train_weights if split == "train" else dev_weights
    # 요청 n이 기본값과 다르면 비례 재조정.
    base_total = sum(desired.values())
    quotas = {
        cat: max(1, round(weight * n / base_total))
        for cat, weight in desired.items()
        if cat in category_items
    }
    # rounding 보정
    while sum(quotas.values()) < n:
        cat = max(quotas, key=lambda c: desired.get(c, 1))
        quotas[cat] += 1
    while sum(quotas.values()) > n:
        cat = max(
            (c for c in quotas if quotas[c] > 1),
            key=lambda c: quotas[c],
        )
        quotas[cat] -= 1

    rows = []
    counters: dict[str, int] = defaultdict(int)

    for category, quota in quotas.items():
        pool = category_items[category][:]
        rng.shuffle(pool)
        for _ in range(quota):
            initials, target, same_group = pool[counters[category] % len(pool)]
            counters[category] += 1

            requested_count = COUNTS[len(rows) % len(COUNTS)]
            alternatives = [x for x in same_group if x["text"] != target["text"]]
            rng.shuffle(alternatives)
            candidates = [target["text"]] + [x["text"] for x in alternatives]
            candidates = candidates[:requested_count]

            rows.append(
                {
                    "id": f"{split.upper()}{len(rows)+1:04d}",
                    "split": split,
                    "initials": initials,
                    "requested_count": requested_count,
                    "target": target["text"],
                    "category": category,
                    "candidates": candidates,
                }
            )

    rng.shuffle(rows)
    for i, row in enumerate(rows, start=1):
        row["id"] = f"{split.upper()}{i:04d}"
    return rows

def build_hard(groups: dict[str, list[dict]], n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    candidates = []
    for initials, items in groups.items():
        dev_items = [x for x in items if x["split"] == "dev"]
        if not dev_items:
            continue
        score = len(dev_items)
        cats = {x["category"] for x in dev_items}
        if cats & {"medical_communication","pain_discomfort","positioning","ambiguity"}:
            score += 2
        for item in dev_items:
            candidates.append((score, initials, item))

    candidates.sort(key=lambda x: -x[0])
    top = candidates[: max(n * 2, n)]
    rng.shuffle(top)
    top = top[:n]

    rows = []
    context_map = {
        "medical_communication": "병원에서 의료진에게 필요한 상태나 요청을 정확히 전달해야 한다.",
        "pain_discomfort": "신체 불편이나 통증을 정확히 알려야 하는 상황이다.",
        "positioning": "현재 자세가 불편해 보호자의 도움이 필요한 상황이다.",
        "food_drink": "음식이나 음료와 관련된 요구를 전달하는 상황이다.",
        "environment": "주변 환경을 조절해야 하는 상황이다.",
        "ambiguity": "최근 대화 문맥을 이용해 같은 초성의 여러 의미 중 의도를 구분해야 한다.",
    }
    for i, (_, initials, item) in enumerate(top, start=1):
        rows.append(
            {
                "id": f"HARD{i:03d}",
                "target": item["text"],
                "bci_input": initials,
                "partner": "medical_staff" if item["category"] in {
                    "medical_communication","pain_discomfort"
                } else "family",
                "situation": "hospital" if item["category"] == "medical_communication" else (
                    "pain" if item["category"] == "pain_discomfort" else (
                        "positioning" if item["category"] == "positioning" else "general"
                    )
                ),
                "current_sentence": "",
                "recent_context": [
                    context_map.get(item["category"], "일상 의사소통에서 정확한 의도를 전달해야 하는 상황이다.")
                ],
                "top_k": 3,
                "category": item["category"],
            }
        )
    return rows


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--review",
        default="training_v2/reviews/candidate_pool_review_v2.csv",
        help="teacher augmentation을 했다면 teacher_candidate_review.csv 또는 수정한 xlsx를 지정",
    )
    p.add_argument("--train-n", type=int, default=600)
    p.add_argument("--dev-n", type=int, default=100)
    p.add_argument("--hard-n", type=int, default=50)
    p.add_argument("--seed", type=int, default=20260901)
    args = p.parse_args()

    review = load_review(args.review)
    groups = group_rows(review)

    train_groups = {k for k,v in groups.items() if any(x["split"]=="train" for x in v)}
    dev_groups = {k for k,v in groups.items() if any(x["split"]=="dev" for x in v)}
    overlap = train_groups & dev_groups
    if overlap:
        raise RuntimeError(f"TRAIN/DEV initials group leakage: {sorted(overlap)[:20]}")

    train = build_examples(groups, "train", args.train_n, args.seed)
    dev = build_examples(groups, "dev", args.dev_n, args.seed + 1)
    hard = build_hard(groups, args.hard_n, args.seed + 2)

    out = Path("training_v2/data")
    write_jsonl(out/"train_semantic_v2.jsonl", train)
    write_jsonl(out/"dev_semantic_v2.jsonl", dev)
    write_jsonl(out/"hard50_v2.jsonl", hard)

    stats = {
        "approved_candidates": sum(len(v) for v in groups.values()),
        "approved_initial_groups": len(groups),
        "train_initial_groups": len(train_groups),
        "dev_initial_groups": len(dev_groups),
        "train_examples": len(train),
        "dev_examples": len(dev),
        "hard_examples": len(hard),
        "train_category_counts": dict(Counter(x["category"] for x in train)),
        "dev_category_counts": dict(Counter(x["category"] for x in dev)),
    }
    Path("training_v2/artifacts/finalize_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
