from __future__ import annotations

from app.korean.initials import extract_units, fill_mask_constraint_match, spelled_constraint_match
from app.llm.types import (
    CandidateScore,
    GenerationCallResult,
    RankingCallResult,
    TokenUsage,
)
from app.schemas import GeneratedCandidate


MOCK_BANK: dict[str, list[str]] = {
    "ㅅㄹㅎ": ["사랑해", "신뢰해", "서로 해"],
    "ㅁㅈ": ["물 줘", "물 좀", "맥주"],
    "ㄷㅇㅈ": ["도와줘", "다음 주", "들어줘"],
    "ㅂㄲㅈ": ["불 꺼줘", "불 끄자", "불 껐지"],
    "ㅈㅅㅂㄲㅈ": ["자세 바꿔줘", "좌석 바꿔줘", "장소 바꿔줘"],
    "ㄱㅁㅇ": ["고마워", "그만요", "귤 먹어"],
    "ㅇㅍ": ["아파", "양파", "약품"],
    "ㅈㄱㅅㅇ": ["자고 싶어", "지금 싫어", "조금 쉬어"],
    "ㅅㄱㅅㅇ": ["쉬고 싶어", "사고 싶어", "살고 싶어"],
    "ㅇㄴㅁㅎ": ["오늘 뭐 해", "오늘 뭘 해", "오늘 뭐함"],
    "ㄴㅇㅁㅎ": ["내일 뭐 해", "내일 뭘 해", "내일 뭐함"],
    "ㄷㅅㅁㅎㅈ": ["다시 말해줘", "더 설명해줘", "다 설명해줘"],
    "ㅊㅊㅎㅁㅎㅈ": ["천천히 말해줘", "천천히만 해줘", "천천히 말하죠"],
}


def _norm(text: str) -> str:
    return "".join(str(text or "").split()).lower()


def _context_bonus(candidate: str, context: str) -> float:
    c = _norm(candidate)
    ctx = _norm(context)
    bonus = 0.0

    if c and c in ctx:
        bonus += 0.45

    rules = {
        "사랑해": ["좋아", "사랑", "애정"],
        "물 줘": ["목말", "목이말", "물", "마시"],
        "도와줘": ["자세", "불편", "혼자", "도와", "positioning"],
        "다음 주": ["다음주", "약속", "일정", "schedule"],
        "불 꺼줘": ["불", "자려고", "잠", "끄"],
        "자세 바꿔줘": ["자세", "불편", "눕", "positioning"],
        "아파": ["통증", "아프", "pain"],
    }
    for keyword in rules.get(candidate, []):
        if keyword in ctx:
            bonus += 0.45
            break

    return min(bonus, 0.50)


class MockLanguageModelClient:
    """Deterministic demo/test client. No external API calls."""

    def __init__(self):
        self.generator_model_name = "mock-generator"
        self.ranker_model_name = "mock-ranker"

    def generate_candidates(self, initials: str, count: int) -> GenerationCallResult:
        return GenerationCallResult(
            candidates=list(MOCK_BANK.get(initials, []))[:count],
            usage=TokenUsage(input_tokens=0, output_tokens=0),
        )

    def generate_recovery_candidates(
        self,
        initials: str,
        count: int,
        *,
        spelled: dict[int, str] | None = None,
        reference_text: str | None = None,
        target_index: int | None = None,
        context: str = "",
    ) -> GenerationCallResult:
        """Best-effort deterministic recovery so MOCK_MODE stays fully clickable
        in local dev/demo without any network calls. Real accuracy comes from the
        cloud recovery path in OpenAILanguageModelClient; this only needs to keep
        the UI from dead-ending during offline demos."""
        pool = list(MOCK_BANK.get(initials, []))

        if spelled:
            pool = [t for t in pool if spelled_constraint_match(t, spelled)]
            if not pool:
                # Synthesize a single trivially-matching candidate so KeywordAE
                # demos still show *something* even when the tiny mock bank has
                # no natural match for this initials+spelling combination.
                units = list(initials)
                for index, syllable in spelled.items():
                    if 0 <= index < len(units):
                        units[index] = syllable
                pool = ["".join(units)]

        if reference_text is not None and target_index is not None:
            pool = [t for t in pool if fill_mask_constraint_match(t, reference_text, target_index)]
            if not pool:
                ref_units = extract_units(reference_text)
                if 0 <= target_index < len(ref_units):
                    swapped = list(ref_units)
                    swapped[target_index] = "?"
                    pool = ["".join(swapped)]

        return GenerationCallResult(
            candidates=pool[:count],
            usage=TokenUsage(input_tokens=0, output_tokens=0),
        )

    def rank_candidates(
        self,
        candidates: list[GeneratedCandidate],
        context: str,
    ) -> RankingCallResult:
        total = max(len(candidates), 1)
        scores: list[CandidateScore] = []

        for i, candidate in enumerate(candidates):
            order_bonus = ((total - i) / total) * 0.08
            context_bonus = _context_bonus(candidate.text, context)
            scores.append(
                CandidateScore(
                    candidate_id=candidate.candidate_id,
                    context_score=min(1.0, 0.50 + order_bonus + context_bonus),
                    intent_score=min(1.0, 0.52 + order_bonus + context_bonus),
                    naturalness_score=min(1.0, 0.80 + order_bonus),
                    partner_score=min(1.0, 0.70 + context_bonus * 0.3),
                )
            )

        return RankingCallResult(
            scores=scores,
            usage=TokenUsage(input_tokens=0, output_tokens=0),
        )
