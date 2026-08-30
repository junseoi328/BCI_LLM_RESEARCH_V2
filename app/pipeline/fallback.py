from __future__ import annotations

from app.schemas import GeneratedCandidate


LOCAL_PHRASE_BANK = {
    "ㄷㅇㅈ": ["도와줘", "들어줘", "다음 주"],
    "ㅁㅈ": ["물 줘", "뭐지", "맞지"],
    "ㅂㄲㅈ": ["불 꺼줘"],
    "ㅈㅅㅂㄲㅈ": ["자세 바꿔줘"],
    "ㅁㅁㄹ": ["목 말라"],
    "ㅊㅇ": ["추워"],
    "ㄷㅇ": ["더워"],
    "ㄱㅁㅇ": ["고마워"],
    "ㅅㄹㅎ": ["사랑해"],
    "ㅂㄱㅍ": ["배고파"],
    "ㅇㅍ": ["아파"],
    "ㅈㄱㅅㅇ": ["자고 싶어"],
}


def local_candidates(initials: str, eeg_score: float | None, start_index: int = 0) -> list[GeneratedCandidate]:
    return [
        GeneratedCandidate(
            candidate_id=f"local-{start_index+i+1}",
            text=text,
            source_initials=initials,
            generation_order=i + 1,
            eeg_score=eeg_score,
        )
        for i, text in enumerate(LOCAL_PHRASE_BANK.get(initials, []))
    ]
