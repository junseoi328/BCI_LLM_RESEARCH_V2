from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    debug_mode: bool = _bool("DEBUG_MODE", False)
    mock_mode: bool = _bool("MOCK_MODE", True)

    openai_api_key: str | None = field(default=os.getenv("OPENAI_API_KEY"), repr=False)
    generator_model: str = os.getenv("OPENAI_GENERATOR_MODEL", os.getenv("GENERATOR_MODEL", os.getenv("OPENAI_MODEL", "gpt-5.6-luna")))
    ranker_model: str = os.getenv("OPENAI_RANKER_MODEL", os.getenv("RANKER_MODEL", os.getenv("OPENAI_MODEL", "gpt-5.6-luna")))
    reasoning_effort: str = os.getenv("OPENAI_REASONING_EFFORT", "low")
    openai_timeout_sec: float = _float("OPENAI_TIMEOUT_SEC", 45.0)
    openai_max_retries: int = _int("OPENAI_MAX_RETRIES", 0)
    max_output_tokens: int = _int("OPENAI_MAX_OUTPUT_TOKENS", 3200)

    generation_count: int = _int("GENERATION_COUNT", 16)
    max_eeg_hypotheses: int = _int("MAX_EEG_HYPOTHESES", 5)
    display_top_k: int = _int("DISPLAY_TOP_K", 3)
    use_llm_ranker: bool = _bool("USE_LLM_RANKER", True)
    allow_local_fallback: bool = _bool("ALLOW_LOCAL_FALLBACK", False)

    # Language ranking weights. These are heuristic ranking weights, not probabilities.
    weight_context: float = _float("WEIGHT_CONTEXT", 0.50)
    weight_intent: float = _float("WEIGHT_INTENT", 0.20)
    weight_naturalness: float = _float("WEIGHT_NATURALNESS", 0.20)
    weight_partner: float = _float("WEIGHT_PARTNER", 0.10)
    weight_eeg: float = _float("WEIGHT_EEG", 0.35)

    diversity_similarity_threshold: float = _float("DIVERSITY_SIMILARITY_THRESHOLD", 0.90)
    eeg_softmax_temperature: float = _float("EEG_SOFTMAX_TEMPERATURE", 1.0)

    hybrid_min_top_score: float = _float("HYBRID_MIN_TOP_SCORE", 0.62)
    hybrid_min_margin: float = _float("HYBRID_MIN_MARGIN", 0.08)

    enable_experiment_log: bool = _bool("ENABLE_EXPERIMENT_LOG", True)
    experiment_log_path: str = os.getenv("EXPERIMENT_LOG_PATH", "logs/experiment.jsonl")

    allowed_origins_raw: str = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

    pipeline_version: str = os.getenv("PIPELINE_VERSION", "0.2.0")
    generator_prompt_version: str = os.getenv("GENERATOR_PROMPT_VERSION", "generator-v2")
    ranker_prompt_version: str = os.getenv("RANKER_PROMPT_VERSION", "ranker-v2")

    @property
    def allowed_origins(self) -> list[str]:
        return [x.strip() for x in self.allowed_origins_raw.split(",") if x.strip()]

    @property
    def log_path(self) -> Path:
        p = Path(self.experiment_log_path)
        return p if p.is_absolute() else ROOT_DIR / p


settings = Settings()
