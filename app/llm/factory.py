from __future__ import annotations

import os

from app.config import settings
from app.llm.demo_resilient_client import DemoResilientLanguageModelClient
from app.llm.mock_client import MockLanguageModelClient
from app.llm.openai_client import OpenAILanguageModelClient


def _true(value: str | bool | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _build_cloud_fallback():
    if _true(os.getenv("BCI_DEMO_MODE", "false")):
        return DemoResilientLanguageModelClient()
    return OpenAILanguageModelClient()


def get_language_model_client():
    """
    Selection priority:
    1) MOCK_MODE=true               -> deterministic test/demo bank (no network, no local model)
    2) LOCAL_BCI_GENERATOR_ENABLED=true -> local fine-tuned generator + phrase memory
       + cloud context ranker (fast path: ~0 network round trips for generation,
       exactly 1 for ranking). Falls back to the cloud-only client below if the
       local model/driver fails to load, so a broken local environment never takes
       the whole service down.
    3) BCI_DEMO_MODE=true           -> OpenAI live + deterministic fallback
    4) otherwise                    -> OpenAI live (generation + ranking both cloud)

    A pure-cloud Render/production deployment should simply leave
    LOCAL_BCI_GENERATOR_ENABLED unset (it defaults to false), since it has no
    GPU/torch dependency there. Local development machines with the fine-tuned
    LoRA adapter can opt in for much lower latency.
    """

    if _true(os.getenv("MOCK_MODE", getattr(settings, "mock_mode", False))):
        return MockLanguageModelClient()

    if _true(os.getenv("LOCAL_BCI_GENERATOR_ENABLED", "false")):
        try:
            from app.llm.local_final_client import LocalGeneratorCloudRankerClient

            return LocalGeneratorCloudRankerClient()
        except Exception as exc:  # missing weights, no XPU/torch, etc.
            print(
                "[FACTORY] LOCAL_BCI_GENERATOR_ENABLED=true 이지만 로컬 생성기 "
                f"로드에 실패해 클라우드 전용 파이프라인으로 폴백합니다: "
                f"{type(exc).__name__}: {exc}"
            )
            return _build_cloud_fallback()

    return _build_cloud_fallback()
