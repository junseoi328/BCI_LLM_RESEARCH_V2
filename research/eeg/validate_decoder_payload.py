from __future__ import annotations
import json
import sys
from pathlib import Path


def validate(data):
    errors = []

    if not isinstance(data.get("trial_id"), str) or not data["trial_id"].strip():
        errors.append("trial_id required")

    if not isinstance(data.get("score_type"), str) or not data["score_type"].strip():
        errors.append("score_type required")

    hs = data.get("hypotheses")
    if not isinstance(hs, list) or not hs:
        errors.append("hypotheses must be non-empty list")
        return errors

    total = 0.0

    for i, h in enumerate(hs):
        if not isinstance(h.get("input"), str) or not h["input"].strip():
            errors.append(f"hypotheses[{i}].input required")

        try:
            s = float(h.get("decoder_score"))
            total += s
        except Exception:
            errors.append(f"hypotheses[{i}].decoder_score must be numeric")

    if data.get("score_type") == "classifier_probability":
        if not (0.95 <= total <= 1.05):
            errors.append(f"probability scores should sum near 1.0 (got {total:.4f})")

    return errors


def main():
    path = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else "research/interfaces/eeg_decoder_contract.json"
    )

    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate(data)

    if errors:
        print("INVALID")
        for e in errors:
            print("-", e)
        raise SystemExit(1)

    print("VALID")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
