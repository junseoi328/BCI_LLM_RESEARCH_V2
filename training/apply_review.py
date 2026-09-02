from __future__ import annotations

import argparse
import csv
from pathlib import Path

from training.common import write_jsonl


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--review", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    rows: list[dict] = []
    with Path(args.review).open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            approved = str(row.get("approved", "")).strip().lower()
            if approved not in {"1", "true", "yes", "y"}:
                continue
            candidates = [x.strip() for x in (row.get("candidates") or "").split("|") if x.strip()]
            rows.append(
                {
                    "id": row["id"],
                    "split": row["split"],
                    "initials": row["initials"],
                    "requested_count": int(row["requested_count"]),
                    "candidates": candidates,
                    "catalog_size": len(candidates),
                }
            )

    write_jsonl(args.output, rows)
    print(f"APPROVED: {len(rows)} -> {args.output}")


if __name__ == "__main__":
    main()
