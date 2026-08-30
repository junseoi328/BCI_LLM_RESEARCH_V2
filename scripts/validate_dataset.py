from __future__ import annotations

import json
from pathlib import Path

from app.korean.initials import extract_initials, validate_initials

PATH = Path(__file__).resolve().parents[1] / "eval" / "datasets" / "sanity_v1.jsonl"


def main() -> None:
    rows = [json.loads(x) for x in PATH.read_text(encoding="utf-8").splitlines() if x.strip()]
    ids = set()
    errors = []
    for row in rows:
        rid = row["id"]
        if rid in ids:
            errors.append(f"duplicate id: {rid}")
        ids.add(rid)
        auto = extract_initials(row["target"])
        given = row.get("bci_input", auto)
        if not validate_initials(given):
            errors.append(f"invalid initials: {rid} {given}")
        if auto != given:
            errors.append(f"mismatch: {rid} target={row['target']} auto={auto} given={given}")
    print(f"rows={len(rows)}")
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print("dataset validation passed")


if __name__ == "__main__":
    main()
