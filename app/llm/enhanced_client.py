from __future__ import annotations

import json
from pathlib import Path

from app.config import settings
from app.errors import LLMServiceError
from app.llm.openai_client import OpenAILanguageModelClient
from app.llm.phrase_memory import PhraseMemory
from app.llm.prompts import GENERATOR_INSTRUCTIONS, build_generator_input
from app.llm.types import GenerationCallResult, RankingCallResult
from app.schemas import GeneratedCandidate
from training.common import normalize_text


class EnhancedLanguageModelClient:
    """
    v7 client:
    - generator: fine-tuned GPT-4.1-mini (or another explicitly supplied FT model)
    - ranker: existing v6.3 ranker (e.g. GPT-5.6 Luna)
    - phrase memory: deterministic candidate coverage boost

    Important:
    The current v6.3 OpenAILanguageModelClient passes GPT-5 reasoning/verbosity
    options. A GPT-4.1-mini fine-tuned generator may not accept those options,
    so v7 generation is called directly with the minimal Responses+JSON Schema
    arguments. Ranking continues to use the existing client unchanged.
    """

    def __init__(
        self,
        generator_model: str,
        ranker_model: str,
        phrase_bank_path: str | Path = "research/phrase_memory/common_phrase_bank.jsonl",
        phrase_limit: int = 6,
    ):
        self.base = OpenAILanguageModelClient(
            generator_model=generator_model,
            ranker_model=ranker_model,
        )
        self.memory = PhraseMemory(phrase_bank_path)
        self.phrase_limit = max(0, phrase_limit)

        self.generator_model_name = generator_model
        self.ranker_model_name = ranker_model
        self.client = self.base.client

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
                        "schema": self.base._generator_schema(),
                    }
                },
                store=False,
            )
            data = json.loads(response.output_text)
            generated = [
                str(x).strip()
                for x in data.get("candidates", [])
                if str(x).strip()
            ]
            usage = self.base._usage(response)
        except Exception as exc:
            if isinstance(exc, LLMServiceError):
                raise
            self.base._raise_clean_error(exc)
            raise AssertionError("unreachable")

        memory = self.memory.candidates(initials, self.phrase_limit)

        merged: list[str] = []
        seen: set[str] = set()
        for text in generated + memory:
            key = normalize_text(text)
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(text)

        # LLM count + a small local-memory allowance.
        return GenerationCallResult(
            candidates=merged[: count + self.phrase_limit],
            usage=usage,
        )

    def rank_candidates(
        self,
        candidates: list[GeneratedCandidate],
        context: str,
    ) -> RankingCallResult:
        return self.base.rank_candidates(candidates, context)
