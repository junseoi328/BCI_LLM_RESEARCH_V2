from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


def is_hit(row, key):
    v = (row.get(key) or "").strip()
    return v in {"1", "2", "3"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    args = ap.parse_args()

    path = Path(args.csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r.get("category", "unknown")].append(r)

    print("=== CATEGORY SUMMARY ===")
    for cat, rs in sorted(by_cat.items()):
        n = len(rs)
        s1 = sum((r.get("strict_rank") or "") == "1" for r in rs) / n
        s3 = sum(is_hit(r, "strict_rank") for r in rs) / n
        n1 = sum((r.get("normalized_rank") or "") == "1" for r in rs) / n
        n3 = sum(is_hit(r, "normalized_rank") for r in rs) / n
        print(f"{cat:24s} n={n:3d} strict@1={s1:.3f} strict@3={s3:.3f} norm@1={n1:.3f} norm@3={n3:.3f}")

    failures = [r for r in rows if not is_hit(r, "normalized_rank")]
    print("\n=== NORMALIZED FAILURES ===")
    for r in failures:
        preds = [r.get("pred_1",""), r.get("pred_2",""), r.get("pred_3","")]
        print(f"{r.get('id')} [{r.get('category')}] {r.get('bci_input')} target={r.get('target')!r} preds={preds} error={r.get('service_error_code') or '-'}")

    errors = Counter((r.get("service_error_code") or "").strip() for r in rows)
    errors.pop("", None)
    print("\n=== SERVICE ERRORS ===")
    if not errors:
        print("none")
    else:
        for k, v in errors.most_common():
            print(k, v)


if __name__ == "__main__":
    main()
