from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from training.common import extract_initials

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def load_model(path: str) -> str:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    model = payload.get("fine_tuned_model")
    if not model:
        raise SystemExit(f"{path}에 fine_tuned_model이 없습니다.")
    return model


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model-state", default="training/artifacts/ft_model.json")
    p.add_argument("--count", type=int, default=16)
    args = p.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY가 없습니다.")

    model = load_model(args.model_state)

    from app.llm.prompts import GENERATOR_INSTRUCTIONS, build_generator_input
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=60.0, max_retries=2)

    schema = {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": args.count,
            }
        },
        "required": ["candidates"],
        "additionalProperties": False,
    }

    cases = [
        "ㅁㅈ", "ㄷㅇㅈ", "ㅈㅅㅂㄲㅈ", "ㅁㅁㄹ",
        "ㅈㄱㅅㅇ", "ㅇㅅㅂㄹㅈ", "ㅊㅁㅇㅇㅈ",
    ]

    invalid = 0
    for initials in cases:
        response = client.responses.create(
            model=model,
            instructions=GENERATOR_INSTRUCTIONS,
            input=build_generator_input(initials, args.count),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "bci_candidate_generation",
                    "strict": True,
                    "schema": schema,
                },
            },
            store=False,
        )
        data = json.loads(response.output_text)
        cands = [str(x).strip() for x in data.get("candidates", []) if str(x).strip()]
        bad = [x for x in cands if extract_initials(x) != initials]
        invalid += len(bad)

        print("=" * 72)
        print("INPUT:", initials)
        print("MODEL:", model)
        print("CANDIDATES:", cands)
        print("INVALID:", bad)

    print("=" * 72)
    print("TOTAL INVALID INITIAL CANDIDATES:", invalid)
    return 0 if invalid == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
