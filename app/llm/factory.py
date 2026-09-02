from __future__ import annotations

import os

from app.config import settings
from app.llm.demo_resilient_client import DemoResilientLanguageModelClient
from app.llm.mock_client import MockLanguageModelClient
from app.llm.openai_client import OpenAILanguageModelClient


def _true(value: str | bool | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def get_language_model_client():
    """
    Selection priority:
    1) MOCK_MODE=true  -> deterministic test/demo bank
    2) BCI_DEMO_MODE=true -> OpenAI live + deterministic fallback
    3) otherwise -> OpenAI live

    Local LoRA is intentionally excluded from the public cloud deployment.
    It remains a research/local branch because the production web service
    should accept arbitrary contexts without Intel-XPU/torch dependencies.
    """

    if _true(os.getenv("MOCK_MODE", getattr(settings, "mock_mode", False))):
        return MockLanguageModelClient()

    if _true(os.getenv("BCI_DEMO_MODE", "false")):
        return DemoResilientLanguageModelClient()

    return OpenAILanguageModelClient()
