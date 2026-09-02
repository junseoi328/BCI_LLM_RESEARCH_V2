from __future__ import annotations

import re
import unicodedata

from app.pipeline.service import BCILanguagePipeline
from app.schemas import PredictionRequest


CASES = [
    ("도와줘", "ㄷㅇㅈ", "family", "positioning", "혼자 자세를 바꾸기 어렵다"),
    ("다음 주", "ㄷㅇㅈ", "friend", "schedule", "다음 주에 약속 잡을까"),
    ("물 줘", "ㅁㅈ", "family", "home", "목이 말라"),
    ("불 꺼줘", "ㅂㄲㅈ", "family", "home", "이제 자려고 해"),
    ("자세 바꿔줘", "ㅈㅅㅂㄲㅈ", "caregiver", "positioning", "현재 자세가 불편해"),
    ("목 말라", "ㅁㅁㄹ", "family", "meal", "물을 마시고 싶어"),
    ("추워", "ㅊㅇ", "family", "home", "방이 너무 춥다"),
    ("고마워", "ㄱㅁㅇ", "family", "general", "도와줘서 고맙다고 말하고 싶다"),
    ("배고파", "ㅂㄱㅍ", "family", "meal", "아직 저녁을 먹지 않았다"),
    ("아파", "ㅇㅍ", "medical_staff", "pain", "통증이 있다는 것을 알려야 한다"),
]


# ============================================================
# 평가용 문자열 정규화
# ============================================================

def normalize_eval_text(text: str) -> str:
    """
    의미를 바꾸지 않는 표면 차이만 제거한다.

    예:
    "도와 줘" -> "도와줘"
    "맞아."   -> "맞아"
    "뭐야?"   -> "뭐야"
    """
    text = unicodedata.normalize("NFC", text or "")
    text = text.strip()

    # 모든 공백 제거
    text = re.sub(r"\s+", "", text)

    # 일반 문장부호 제거
    text = re.sub(
        r"""[.,!?~…'"“”‘’·:;()\[\]{}<>]""",
        "",
        text,
    )

    return text


def normalized_rank(
    target: str,
    predictions: list[str],
) -> int | None:
    target_norm = normalize_eval_text(target)

    for i, pred in enumerate(predictions, start=1):
        if normalize_eval_text(pred) == target_norm:
            return i

    return None


# ============================================================
# Main
# ============================================================

def main() -> None:
    pipeline = BCILanguagePipeline()

    strict_hit1 = 0
    strict_hit3 = 0

    normalized_hit1 = 0
    normalized_hit3 = 0

    for i, (
        target,
        initials,
        partner,
        situation,
        context,
    ) in enumerate(CASES, 1):

        res = pipeline.predict(
            PredictionRequest(
                bci_input=initials,
                partner=partner,
                situation=situation,
                recent_context=[context],
                top_k=3,
            )
        )

        preds = [
            x.text
            for x in res.candidates
        ]

        # ----------------------------------------------------
        # Strict evaluation
        # ----------------------------------------------------

        strict_rank = (
            preds.index(target) + 1
            if target in preds
            else None
        )

        # ----------------------------------------------------
        # Normalized evaluation
        # ----------------------------------------------------

        norm_rank = normalized_rank(
            target,
            preds,
        )

        strict_hit1 += (
            strict_rank == 1
        )

        strict_hit3 += (
            strict_rank is not None
            and strict_rank <= 3
        )

        normalized_hit1 += (
            norm_rank == 1
        )

        normalized_hit3 += (
            norm_rank is not None
            and norm_rank <= 3
        )

        print(
            f"{i:02d}. "
            f"{initials} "
            f"target={target:<10} "
            f"strict_rank={strict_rank} "
            f"norm_rank={norm_rank} "
            f"preds={preds} "
            f"latency={res.latency.total_ms}ms "
            f"fallback={res.fallback}"
        )

    n = len(CASES)

    print()
    print("=" * 70)
    print("SANITY SUMMARY")
    print("=" * 70)

    print(
        f"Strict Acc@1={strict_hit1 / n:.3f}"
    )

    print(
        f"Strict Acc@3={strict_hit3 / n:.3f}"
    )

    print(
        f"Normalized Acc@1={normalized_hit1 / n:.3f}"
    )

    print(
        f"Normalized Acc@3={normalized_hit3 / n:.3f}"
    )


if __name__ == "__main__":
    main()