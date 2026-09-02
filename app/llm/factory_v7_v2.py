from __future__ import annotations

import json
import os
from pathlib import Path

from app.llm.fine_tuned_generator_v2 import FineTunedGeneratorClient
from app.llm.openai_client import OpenAILanguageModelClient


def get_language_model_client_v7():
    enabled = os.getenv("V7_FT_ENABLED","false").strip().lower() in {
        "1","true","yes","on"
    }
    if not enabled:
        return OpenAILanguageModelClient()

    env_model = os.getenv("FT_GENERATOR_MODEL","").strip()
    if env_model:
        ft_model = env_model
    else:
        state = json.loads(
            Path("training_v2/artifacts/ft_model_v2.json").read_text(encoding="utf-8")
        )
        ft_model = str(state.get("fine_tuned_model") or "").strip()

    if not ft_model:
        raise RuntimeError("Fine-tuned generator model ID를 찾지 못했습니다.")

    return FineTunedGeneratorClient(
        generator_model=ft_model,
        ranker_model=os.getenv("RANKER_MODEL","gpt-5.6-luna"),
    )
