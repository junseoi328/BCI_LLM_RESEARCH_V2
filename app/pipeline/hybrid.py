from __future__ import annotations

from app.config import settings
from app.schemas import ExperimentMode, RankedCandidate


def hybrid_action(mode: ExperimentMode, candidates: list[RankedCandidate]) -> str:
    if mode != ExperimentMode.hybrid:
        return "show_candidates"
    if not candidates:
        return "need_more_input"
    top = candidates[0].final_score
    second = candidates[1].final_score if len(candidates) > 1 else 0.0
    margin = top - second
    if top < settings.hybrid_min_top_score or margin < settings.hybrid_min_margin:
        return "need_more_input"
    return "show_candidates"
