from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path

from training_v2.common import (
    extract_initials,
    load_dotenv_if_available,
    normalize_text,
    read_jsonl,
)

TRANSIENT = {"timeout","connection_error","rate_limit","openai_error"}


def main() -> int:
    load_dotenv_if_available()

    p = argparse.ArgumentParser()
    p.add_argument("--pool", default="training_v2/data/seed_all_pool.jsonl")
    p.add_argument("--count", type=int, default=24)
    p.add_argument("--calls-per-initial", type=int, default=1)
    p.add_argument("--max-retries", type=int, default=3)
    p.add_argument("--max-initials", type=int, default=80, help="0이면 전체 initial group")
    p.add_argument("--sleep-sec", type=float, default=0.7)
    p.add_argument("--checkpoint", default="training_v2/artifacts/teacher_checkpoint.json")
    p.add_argument("--output", default="training_v2/reviews/teacher_candidate_review.csv")
    args = p.parse_args()

    from app.llm.openai_client import OpenAILanguageModelClient

    seed_rows = read_jsonl(args.pool)
    seed_by: dict[str, set[str]] = defaultdict(set)
    meta_by: dict[str, dict] = {}
    for row in seed_rows:
        seed_by[row["initials"]].add(row["text"])
        meta_by.setdefault(row["initials"], row)

    checkpoint_path = Path(args.checkpoint)
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    else:
        checkpoint = {"done": {}, "errors": {}}

    client = OpenAILanguageModelClient()
    initials_list = sorted(
        seed_by,
        key=lambda x: (
            0 if meta_by[x]["category"] in {
                "medical_communication","pain_discomfort","positioning","ambiguity"
            } else 1,
            len(seed_by[x]),
            x,
        ),
    )
    if args.max_initials > 0:
        initials_list = initials_list[: args.max_initials]

    for idx, initials in enumerate(initials_list, start=1):
        if initials in checkpoint["done"]:
            print(f"[{idx:03d}/{len(initials_list):03d}] {initials} SKIP")
            continue

        generated: list[str] = []
        error_message = None
        for call_index in range(args.calls_per_initial):
            for attempt in range(1, args.max_retries + 2):
                try:
                    result = client.generate_candidates(initials, args.count)
                    generated.extend(result.candidates)
                    error_message = None
                    break
                except Exception as exc:
                    code = str(getattr(exc, "code", type(exc).__name__))
                    error_message = f"{type(exc).__name__}:{exc}"
                    if code in TRANSIENT and attempt <= args.max_retries:
                        wait = 2 ** (attempt - 1)
                        print(f"{initials} {code} retry after {wait}s")
                        time.sleep(wait)
                        continue
                    break

        valid = []
        seen = {normalize_text(x) for x in seed_by[initials]}
        for text in generated:
            text = str(text).strip()
            if extract_initials(text) != initials:
                continue
            key = normalize_text(text)
            if not key or key in seen:
                continue
            seen.add(key)
            valid.append(text)

        checkpoint["done"][initials] = valid
        if error_message:
            checkpoint["errors"][initials] = error_message
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text(
            json.dumps(checkpoint, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(
            f"[{idx:03d}/{len(initials_list):03d}] {initials} "
            f"seed={len(seed_by[initials])} teacher_new={len(valid)}"
        )
        time.sleep(args.sleep_sec)

    dst = Path(args.output)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8-sig", newline="") as f:
        fields = [
            "split","category","initials","text","source",
            "approved","priority","note",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()

        # seed는 이미 사람 curated → approved 1
        for row in seed_rows:
            w.writerow(
                {
                    "split": row["split"],
                    "category": row["category"],
                    "initials": row["initials"],
                    "text": row["text"],
                    "source": "curated_seed_v2",
                    "approved": 1,
                    "priority": "high" if row["category"] in {
                        "medical_communication","pain_discomfort","positioning","ambiguity"
                    } else "normal",
                    "note": "",
                }
            )

        # teacher output은 반드시 사람이 한번 확인 → approved 0
        for initials, texts in checkpoint["done"].items():
            meta = meta_by[initials]
            for text in texts:
                w.writerow(
                    {
                        "split": meta["split"],
                        "category": meta["category"],
                        "initials": initials,
                        "text": text,
                        "source": "teacher_generator",
                        "approved": 0,
                        "priority": "review",
                        "note": "",
                    }
                )

    print("OUTPUT:", dst)
    print("teacher_generator 행은 approved=0입니다. 자연스러운 표현만 1로 승인한 뒤 finalize 하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
