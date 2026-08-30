from __future__ import annotations

from app.config import settings
from app.llm.types import CandidateScore
from app.schemas import GeneratedCandidate, RankedCandidate


def language_score(score: CandidateScore) -> float:
    weights = [
        settings.weight_context,
        settings.weight_intent,
        settings.weight_naturalness,
        settings.weight_partner,
    ]
    values = [
        score.context_score,
        score.intent_score,
        score.naturalness_score,
        score.partner_score,
    ]
    denom = sum(weights) or 1.0
    value = sum(w * v for w, v in zip(weights, values, strict=True)) / denom
    return max(0.0, min(1.0, value))


def final_score(lang_score: float, eeg_score: float | None) -> float:
    # A heuristic fusion score; do not call this a calibrated posterior probability.
    if eeg_score is None:
        return max(0.0, min(1.0, lang_score))
    w = max(0.0, min(1.0, settings.weight_eeg))
    return max(0.0, min(1.0, w * eeg_score + (1.0 - w) * lang_score))


def local_rank_scores(candidates: list[GeneratedCandidate]) -> list[CandidateScore]:
    """Deterministic ranker fallback used only when the LLM ranker is unavailable."""
    out: list[CandidateScore] = []
    for i, c in enumerate(candidates):
        order_score = max(0.2, 0.90 - 0.025 * i)
        brevity_bonus = max(0.0, 1.0 - max(0, len(c.text) - 8) * 0.03)
        naturalness = max(0.2, 0.75 * order_score + 0.25 * brevity_bonus)
        out.append(
            CandidateScore(
                candidate_id=c.candidate_id,
                context_score=0.50,
                intent_score=0.50,
                naturalness_score=naturalness,
                partner_score=0.50,
            )
        )
    return out


def merge_scores(
    candidates: list[GeneratedCandidate],
    score_rows: list[CandidateScore],
) -> list[RankedCandidate]:
    by_id = {s.candidate_id: s for s in score_rows}
    fallback_scores = {s.candidate_id: s for s in local_rank_scores(candidates)}
    ranked: list[RankedCandidate] = []

    for c in candidates:
        score = by_id.get(c.candidate_id, fallback_scores[c.candidate_id])
        lang = language_score(score)
        final = final_score(lang, c.eeg_score)
        ranked.append(
            RankedCandidate(
                candidate_id=c.candidate_id,
                text=c.text,
                rank=0,
                matched_initials=c.source_initials,
                eeg_score=c.eeg_score,
                context_score=score.context_score,
                intent_score=score.intent_score,
                naturalness_score=score.naturalness_score,
                partner_score=score.partner_score,
                language_score=lang,
                final_score=final,
            )
        )

    ranked.sort(key=lambda x: (-x.final_score, x.text))
    return [c.model_copy(update={"rank": i + 1}) for i, c in enumerate(ranked)]
