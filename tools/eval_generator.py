"""문장 후보 생성기(LLM) 실측: 프롬프트·후보 수별 유효율·정답률·지연.

실제 OpenAI 호출을 하므로 .env 의 OPENAI_API_KEY 가 필요하다(호출당 수백 토큰).
    python tools/eval_generator.py [문장목록.txt] [--n 40]
문장목록: 한 줄에 목표 문장 하나. 초성열은 여기서 계산한다.
"""
from __future__ import annotations

import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.korean.initials import extract_initials  # noqa: E402
from app.llm import openai_client as oc  # noqa: E402
from app.llm import prompts  # noqa: E402
from app.pipeline.filter import canonicalize, filter_candidates  # noqa: E402
from app.schemas import GeneratedCandidate  # noqa: E402

DEFAULT = ["물 좀 주세요", "배 아파요", "고마워", "너무 아파", "이불 좀 갖다 줘", "허리가 뻐근해", "해열제 주세요",
           "다리 좀 주물러줘", "속이 쓰려", "많이 불안해", "오늘 재밌었어", "휴지 갖다 주세요"]


BASE = prompts.build_generator_input


def slot_input(initials: str, count: int) -> str:
    """후보안: 음절 수와 음절별 초성을 칸으로 풀어 준다(모델이 자모 토큰을 세다 틀리는 것을 줄인다)."""
    units = [c for c in initials if not c.isspace()]
    slots = " ".join(f"{i + 1}={c}" for i, c in enumerate(units))
    return (
        f"초성열: {initials}\n"
        f"음절 수: {len(units)} (띄어쓰기 제외)\n"
        f"음절별 초성: {slots}\n"
        f"내부 생성 후보 수: {count}\n"
        "각 후보는 띄어쓰기를 빼고 정확히 위 음절 수의 한글 음절이며, n번째 음절의 첫 자음이 n번째 초성과 같아야 한다"
        "(완성 글자가 주어진 칸은 그 글자 그대로). 쓰기 전에 음절마다 대조하고 어긋난 후보는 버려라.\n"
        "초성열에 대응 가능한 서로 다른 한국어 발화 후보를 생성하라."
    )


def run(texts: list[str], builder, count: int, retry: bool = False) -> dict:
    oc.build_generator_input = builder
    client = oc.OpenAILanguageModelClient()

    def one(target: str):
        ini = extract_initials(target)
        t = time.perf_counter()
        try:
            res = client.generate_candidates(ini, count)
            raw = res.candidates
            if retry and not filter_candidates([GeneratedCandidate(candidate_id=f"r{i}", text=x, source_initials=ini, generation_order=i + 1)
                                                for i, x in enumerate(raw)], ini):
                raw = client.generate_candidates(ini, count).candidates
        except Exception as exc:  # 한 건 실패가 전체 측정을 멈추지 않게
            return target, [], 0.0, type(exc).__name__
        ms = (time.perf_counter() - t) * 1000
        cands = [GeneratedCandidate(candidate_id=f"c{i}", text=x, source_initials=ini, generation_order=i + 1)
                 for i, x in enumerate(raw)]
        valid = [c.text for c in filter_candidates(cands, ini)]
        return target, valid, ms, None

    with ThreadPoolExecutor(6) as pool:
        rows = list(pool.map(one, texts))
    goal = [canonicalize(t) for t, *_ in rows]
    valid = [v for _, v, _, _ in rows]
    return {
        "유효 후보 평균": round(statistics.mean(len(v) for v in valid), 2),
        "0개 비율%": round(100 * sum(not v for v in valid) / len(rows), 1),
        "정답 포함%": round(100 * sum(g in {canonicalize(x) for x in v} for g, v in zip(goal, valid)) / len(rows), 1),
        "정답 top3%": round(100 * sum(g in {canonicalize(x) for x in v[:3]} for g, v in zip(goal, valid)) / len(rows), 1),
        "지연 중앙값ms": round(statistics.median(ms for _, _, ms, e in rows if not e) if any(not r[3] for r in rows) else 0),
        "오류": sum(bool(e) for *_, e in rows),
    }


if __name__ == "__main__":
    print("모델", oc.settings.generator_model, "· reasoning", oc.settings.reasoning_effort, flush=True)
    args = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and sys.argv[i - 1] not in ("--n", "--only")]
    texts = [l.strip() for l in open(args[0], encoding="utf-8") if l.strip()] if args else DEFAULT
    if "--n" in sys.argv:
        texts = texts[: int(sys.argv[sys.argv.index("--n") + 1])]
    configs = [("기본", BASE, 5), ("기본", BASE, 8), ("음절칸", slot_input, 5), ("음절칸", slot_input, 8), ("재시도", BASE, 5)]
    if "--only" in sys.argv:  # 예: --only 기본5,음절칸8
        keep = sys.argv[sys.argv.index("--only") + 1].split(",")
        configs = [c for c in configs if f"{c[0]}{c[2]}" in keep]
    for name, builder, count in configs:
        print(name, f"후보수={count}", run(texts, builder, count, retry=name == "재시도"), flush=True)
