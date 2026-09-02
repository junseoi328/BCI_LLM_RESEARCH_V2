from __future__ import annotations

import json
from pathlib import Path

from app.config import settings
from app.errors import LLMServiceError
from app.llm.openai_client import OpenAILanguageModelClient
from app.llm.prompts import GENERATOR_INSTRUCTIONS, build_generator_input
from app.llm.types import GenerationCallResult, RankingCallResult
from app.schemas import GeneratedCandidate


class FineTunedGeneratorClient:
    """
    Current pipeline-compatible client:
    - generator: fine-tuned GPT-4.1-mini
    - ranker: current GPT-5.6 Luna
    """

    def __init__(self, generator_model: str, ranker_model: str = "gpt-5.6-luna"):
        self.generator_model_name = generator_model
        self.ranker_model_name = ranker_model
        self._base = OpenAILanguageModelClient(
            generator_model=generator_model,
            ranker_model=ranker_model,
        )
        self.client = self._base.client

    @staticmethod
    def _schema() -> dict:
        return {
            "type": "object",
            "properties": {
                "candidates": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            },
            "required": ["candidates"],
            "additionalProperties": False,
        }

    def generate_candidates(self, initials: str, count: int) -> GenerationCallResult:
        try:
            response = self.client.responses.create(
                model=self.generator_model_name,
                instructions=GENERATOR_INSTRUCTIONS,
                input=build_generator_input(initials, count),
                max_output_tokens=settings.max_output_tokens,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "bci_candidate_generation",
                        "strict": True,
                        "schema": self._schema(),
                    }
                },
                store=False,
            )
            payload = json.loads(response.output_text)
            candidates = [
                str(x).strip()
                for x in payload.get("candidates", [])
                if str(x).strip()
            ]
            return GenerationCallResult(
                candidates=candidates[:count],
                usage=self._base._usage(response),
            )
        except Exception as exc:
            if isinstance(exc, LLMServiceError):
                raise
            self._base._raise_clean_error(exc)
            raise AssertionError("unreachable")

    def rank_candidates(
        self,
        candidates: list[GeneratedCandidate],
        context: str,
    ) -> RankingCallResult:
        return self._base.rank_candidates(candidates, context)


def load_ft_model(
    state_path: str = "training_v2/artifacts/ft_model_v2.json",
) -> str:
    payload = json.loads(Path(state_path).read_text(encoding="utf-8"))
    model = str(payload.get("fine_tuned_model") or "").strip()
    if not model:
        raise RuntimeError("fine_tuned_model 없음")
    return model
