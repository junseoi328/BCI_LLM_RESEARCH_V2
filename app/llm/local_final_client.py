from __future__ import annotations
from local_ft.inference_final import LocalBCIGenerator

from app.llm.openai_client import (
    OpenAILanguageModelClient,
)

from app.llm.types import (
    GenerationCallResult,
    RankingCallResult,
    TokenUsage,
)

from app.schemas import (
    GeneratedCandidate,
)

from local_ft.inference import (
    LocalBCIGenerator,
)


class LocalGeneratorCloudRankerClient:
    """
    Final Hybrid BCI Language Client

    Generator:
        Local Qwen + Fine-tuned LoRA

    Ranker:
        OpenAI GPT-5.6 Luna

    구조:
        BCI initials
        -> Local Generator
        -> deterministic Hangul filtering
        -> Luna context ranker
        -> Top-K
    """

    def __init__(self):

        # ----------------------------------------
        # LOCAL FINE-TUNED GENERATOR
        # ----------------------------------------

        self.local_generator = (
            LocalBCIGenerator()
        )

        # ----------------------------------------
        # CLOUD CONTEXT RANKER
        # ----------------------------------------

        self.cloud_ranker = (
            OpenAILanguageModelClient()
        )

        # ========================================
        # IMPORTANT:
        # BCILanguagePipeline이 반드시 요구하는
        # model interface attributes
        # ========================================

        base_name = (
            self.local_generator
            .meta
            .get(
                "base_model",
                "qwen2.5-0.5b",
            )
        )

        self.generator_model_name = (
            f"local-lora:{base_name}"
        )

        self.ranker_model_name = (
            self.cloud_ranker
            .ranker_model_name
        )

    # ============================================
    # GENERATION
    # ============================================

    def generate_candidates(
        self,
        initials: str,
        count: int,
    ) -> GenerationCallResult:

        candidates = (
            self.local_generator.generate(
                initials=initials,
                count=count,
            )
        )

        # Local inference이므로
        # OpenAI token 사용량 = 0
        usage = TokenUsage(
            input_tokens=0,
            output_tokens=0,
        )

        return GenerationCallResult(
            candidates=candidates,
            usage=usage,
        )

    # ============================================
    # CONTEXT RANKING
    # ============================================

    def rank_candidates(
        self,
        candidates: list[GeneratedCandidate],
        context: str,
    ) -> RankingCallResult:

        return (
            self.cloud_ranker
            .rank_candidates(
                candidates,
                context,
            )
        )