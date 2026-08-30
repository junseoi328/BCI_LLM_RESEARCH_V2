from __future__ import annotations

from app.llm.types import CandidateScore, GenerationCallResult, RankingCallResult, TokenUsage
from app.schemas import GeneratedCandidate


class MockLanguageModelClient:
    generator_model_name = "mock-generator"
    ranker_model_name = "mock-ranker"

    BANK = {
        "ㄷㅇㅈ": ["도와줘", "들어줘", "다음 주", "되어줘", "돌아줘"],
        "ㅁㅈ": ["물 줘", "뭐지", "맞지", "먼저", "문제"],
        "ㅂㄲㅈ": ["불 꺼줘", "방 꺼줘"],
        "ㅈㅅㅂㄲㅈ": ["자세 바꿔줘"],
        "ㅁㅁㄹ": ["목 말라", "뭐 먹을래"],
        "ㅊㅇ": ["추워"],
        "ㄷㅇ": ["더워"],
        "ㄱㅁㅇ": ["고마워"],
        "ㅅㄹㅎ": ["사랑해"],
        "ㅈㄱㅅㅇ": ["자고 싶어"],
        "ㅂㄱㅍ": ["배고파"],
        "ㅇㅍ": ["아파"],
    }

    def generate_candidates(self, initials: str, count: int) -> GenerationCallResult:
        texts = list(self.BANK.get(initials, []))
        while len(texts) < count:
            texts.append(f"무효후보{len(texts)+1}")
        return GenerationCallResult(candidates=texts[:count], usage=TokenUsage())

    def rank_candidates(self, candidates: list[GeneratedCandidate], context: str) -> RankingCallResult:
        context_lower = context.lower()
        scores: list[CandidateScore] = []
        for i, c in enumerate(candidates):
            base = max(0.2, 0.80 - i * 0.025)
            context_score = base

            # Deterministic mock behavior only for integration tests; not research performance.
            if "다음 주" in context and c.text == "다음 주":
                context_score = 0.99
            if any(k in context for k in ["자세", "혼자", "도움"] ) and c.text == "도와줘":
                context_score = 0.96
            if any(k in context for k in ["목이 말", "물"] ) and c.text == "물 줘":
                context_score = 0.98
            if "자고" in context and c.text == "자고 싶어":
                context_score = 0.98

            scores.append(
                CandidateScore(
                    candidate_id=c.candidate_id,
                    context_score=context_score,
                    intent_score=context_score,
                    naturalness_score=max(0.45, 0.90 - i * 0.015),
                    partner_score=0.88,
                )
            )
        return RankingCallResult(scores=scores, usage=TokenUsage())
