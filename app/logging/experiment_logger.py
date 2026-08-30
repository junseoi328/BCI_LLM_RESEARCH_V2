from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

from app.config import settings
from app.schemas import PredictionRequest, PredictionResponse

_LOCK = threading.Lock()


def log_prediction(request: PredictionRequest, response: PredictionResponse) -> None:
    if not settings.enable_experiment_log:
        return

    path = settings.log_path
    path.parent.mkdir(parents=True, exist_ok=True)

    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": response.request_id,
        "session_id": request.session_id,
        "trial_id": request.trial_id,
        "experiment_mode": request.experiment_mode.value,
        "input_mode": request.input_mode.value,
        "input": request.bci_input,
        "partner": request.partner.value,
        "situation": request.situation.value,
        "context_level": request.context_level.value,
        "eeg_score_type": request.eeg_score_type.value,
        "eeg_hypotheses": [h.model_dump() for h in (request.eeg_hypotheses or [])],
        "final_candidates": [
            {
                "candidate_id": c.candidate_id,
                "text": c.text,
                "rank": c.rank,
                "matched_initials": c.matched_initials,
                "eeg_score": c.eeg_score,
                "language_score": c.language_score,
                "final_score": c.final_score,
            }
            for c in response.candidates
        ],
        "fallback": response.fallback,
        "hybrid_action": response.hybrid_action,
        "latency": response.latency.model_dump(),
        "usage": response.usage.model_dump(),
        "generator_model": response.generator_model,
        "ranker_model": response.ranker_model,
        "pipeline_version": response.pipeline_version,
        "generator_prompt_version": response.generator_prompt_version,
        "ranker_prompt_version": response.ranker_prompt_version,
        "warnings": response.warnings,
    }

    # Do not log raw API keys or participant-identifying personal data.
    with _LOCK:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
