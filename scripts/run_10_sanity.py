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


def main() -> None:
    pipeline = BCILanguagePipeline()
    hit1 = hit3 = 0
    for i, (target, initials, partner, situation, context) in enumerate(CASES, 1):
        res = pipeline.predict(PredictionRequest(
            bci_input=initials,
            partner=partner,
            situation=situation,
            recent_context=[context],
            top_k=3,
        ))
        preds = [x.text for x in res.candidates]
        rank = preds.index(target) + 1 if target in preds else None
        hit1 += rank == 1
        hit3 += rank is not None and rank <= 3
        print(f"{i:02d}. {initials} target={target:<10} rank={rank} preds={preds} latency={res.latency.total_ms}ms fallback={res.fallback}")
    print(f"Acc@1={hit1/len(CASES):.3f}")
    print(f"Acc@3={hit3/len(CASES):.3f}")


if __name__ == "__main__":
    main()
