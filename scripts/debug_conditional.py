from __future__ import annotations

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


def main():
    pipeline = BCILanguagePipeline()

    for i, (target, initials, partner, situation, context) in enumerate(CASES, 1):

        res = pipeline.predict(
            PredictionRequest(
                bci_input=initials,
                partner=partner,
                situation=situation,
                recent_context=[context],
                top_k=3,
            )
        )

        print()
        print("=" * 70)
        print(f"{i:02d}. {initials}")
        print(f"TARGET: {target}")
        print(f"PREDS : {[x.text for x in res.candidates]}")
        print(f"LATENCY: {res.latency.total_ms} ms")

        debug = res.debug or {}

        generations = debug.get(
            "generation",
            []
        )

        for row in generations:

            print("-" * 70)

            print(
                "SOURCE:",
                row.get("source")
            )

            if row.get("skipped"):
                print("DIVERSITY SKIPPED: True")
                print(
                    "BASE VALID COUNT:",
                    row.get("base_valid_count")
                )
                print(
                    "FIRST TOKEN RATIO:",
                    row.get("first_token_ratio")
                )
            else:
                print(
                    "RAW COUNT:",
                    row.get("raw_count")
                )
                print(
                    "VALID COUNT:",
                    row.get("valid_count")
                )
                print(
                    "VALID:",
                    row.get("valid")
                )


if __name__ == "__main__":
    main()