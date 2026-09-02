from __future__ import annotations

import json
import os
from pathlib import Path

from app.config import settings
from app.llm.enhanced_client import EnhancedLanguageModelClient
from app.llm.openai_client import OpenAILanguageModelClient


def _load_ft_model() -> str | None:
    env_model = os.getenv("FT_GENERATOR_MODEL", "").strip()
    if env_model:
        return env_model

    state_path = Path(
        os.getenv(
            "FT_MODEL_STATE",
            "training/artifacts/ft_model.json",
        )
    )
    if state_path.exists():
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            model = str(payload.get("fine_tuned_model") or "").strip()
            if model:
                return model
        except Exception:
            pass
    return None


def get_language_model_client_v7():
    # Mock mode는 기존 factory로 위임하여 기존 테스트를 깨지 않음.
    if getattr(settings, "mock_mode", False):
        from app.llm.factory import get_language_model_client
        return get_language_model_client()

    enabled = os.getenv("V7_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }
    if not enabled:
        return OpenAILanguageModelClient()

    ft_model = _load_ft_model()
    if not ft_model:
        raise RuntimeError(
            "V7_ENABLED=true 이지만 FT_GENERATOR_MODEL/ft_model.json을 찾지 못했습니다."
        )

    ranker_model = getattr(settings, "ranker_model", None) or getattr(
        settings, "generator_model", None
    )

    return EnhancedLanguageModelClient(
        generator_model=ft_model,
        ranker_model=ranker_model,
        phrase_bank_path=os.getenv(
            "PHRASE_BANK_PATH",
            "research/phrase_memory/common_phrase_bank.jsonl",
        ),
        phrase_limit=int(os.getenv("PHRASE_MEMORY_LIMIT", "6")),
    )
