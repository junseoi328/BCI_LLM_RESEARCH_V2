from __future__ import annotations

from app.errors import LLMServiceError
from app.llm.mock_client import MockLanguageModelClient
from app.llm.openai_client import OpenAILanguageModelClient
from app.llm.types import GenerationCallResult, RankingCallResult
from app.schemas import GeneratedCandidate


class DemoResilientLanguageModelClient:
    """
    Production demo mode:
    - Primary: OpenAI candidate generation + context ranking
    - Fallback: deterministic demo bank for known presentation cases

    This keeps arbitrary inputs available when OpenAI is healthy,
    while retaining a safe demo path for known examples.
    """

    def __init__(self):
        self.live = OpenAILanguageModelClient()
        self.mock = MockLanguageModelClient()
        self.generator_model_name = self.live.generator_model_name
        self.ranker_model_name = self.live.ranker_model_name

    def generate_candidates(self, initials: str, count: int) -> GenerationCallResult:
        try:
            result = self.live.generate_candidates(initials, count)
            if result.candidates:
                return result
        except LLMServiceError as exc:
            print(f"[BCI_DEMO] generator fallback: {exc.code}")

        return self.mock.generate_candidates(initials, count)

    def rank_candidates(
        self,
        candidates: list[GeneratedCandidate],
        context: str,
    ) -> RankingCallResult:
        try:
            return self.live.rank_candidates(candidates, context)
        except LLMServiceError as exc:
            print(f"[BCI_DEMO] ranker fallback: {exc.code}")
            return self.mock.rank_candidates(candidates, context)
