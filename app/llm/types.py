from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.schemas import GeneratedCandidate


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class GenerationCallResult:
    candidates: list[str]
    usage: TokenUsage
    fallback: str = "none"


@dataclass
class CandidateScore:
    candidate_id: str
    context_score: float
    intent_score: float
    naturalness_score: float
    partner_score: float


@dataclass
class RankingCallResult:
    scores: list[CandidateScore]
    usage: TokenUsage
    fallback: str = "none"


class LanguageModelClient(Protocol):
    generator_model_name: str
    ranker_model_name: str

    def generate_candidates(self, initials: str, count: int) -> GenerationCallResult: ...

    def rank_candidates(self, candidates: list[GeneratedCandidate], context: str) -> RankingCallResult: ...
