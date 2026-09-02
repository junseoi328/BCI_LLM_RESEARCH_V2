from __future__ import annotations

import argparse
import json
from pathlib import Path

from training_v2.common import read_jsonl


FALLBACK_INSTRUCTIONS = """너는 한국어 BCI Speller의 후보 생성기다.
입력된 초성열과 정확히 일치하는 자연스러운 한국어 의사소통 후보를 생성한다.
후보끼리 의미와 표현이 지나치게 중복되지 않게 한다.
출력은 반드시 JSON 객체 {"candidates":[...]} 형식이다."""


def load_runtime_prompt():
    try:
        from app.llm.prompts import GENERATOR_INSTRUCTIONS, build_generator_input
        return GENERATOR_INSTRUCTIONS, build_generator_input, True
    except Exception:
        def build_generator_input(initials: str, count: int) -> str:
            return (
                f"BCI 초성 입력: {initials}\n"
                f"후보 수: 최대 {count}\n"
                "초성이 정확히 일치하는 자연스러운 한국어 발화 후보를 생성하세요."
            )
        return FALLBACK_INSTRUCTIONS, build_generator_input, False


def export(src: Path, dst: Path) -> int:
    instructions, build_input, runtime = load_runtime_prompt()
    rows = read_jsonl(src)
    dst.parent.mkdir(parents=True, exist_ok=True)

    with dst.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            assistant = json.dumps(
                {"candidates": row["candidates"]},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            payload = {
                "messages": [
                    {"role": "system", "content": instructions},
                    {
                        "role": "user",
                        "content": build_input(
                            row["initials"],
                            int(row["requested_count"]),
                        ),
                    },
                    {"role": "assistant", "content": assistant},
                ]
            }
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    print(f"{dst}: {len(rows)} examples, runtime_prompt={runtime}")
    return len(rows)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--train", default="training_v2/data/train_semantic_v2.jsonl")
    p.add_argument("--dev", default="training_v2/data/dev_semantic_v2.jsonl")
    p.add_argument("--out-dir", default="training_v2/data/openai")
    args = p.parse_args()

    out = Path(args.out_dir)
    export(Path(args.train), out/"train_sft_v2.jsonl")
    export(Path(args.dev), out/"dev_sft_v2.jsonl")


if __name__ == "__main__":
    main()
