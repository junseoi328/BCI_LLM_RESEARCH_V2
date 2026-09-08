from __future__ import annotations

import math

from app.config import settings
from app.schemas import EEGScoreType, PredictionRequest


def _softmax(values: list[float], temperature: float = 1.0) -> list[float]:
    if not values:
        return []
    t = max(1e-6, temperature)
    scaled = [v / t for v in values]
    m = max(scaled)
    exps = [math.exp(v - m) for v in scaled]
    total = sum(exps)
    return [x / total for x in exps]


def normalized_eeg_hypotheses(request: PredictionRequest) -> list[tuple[str, float | None]]:
    """Return (initials, normalized evidence in [0,1]).

    If no EEG distribution is supplied, the typed BCI input is used with eeg_score=None.
    This avoids pretending a manually supplied input has EEG probability 1.0.
    """
    if not request.eeg_hypotheses:
        return [(request.bci_input, None)]

    # Decoder outputs need not arrive sorted; truncate only after ranking.
    hyps = sorted(request.eeg_hypotheses, key=lambda h: h.score, reverse=True)[: settings.max_eeg_hypotheses]
    raw = [float(h.score) for h in hyps]

    if request.eeg_score_type == EEGScoreType.probability:
        clipped = [max(0.0, min(1.0, x)) for x in raw]
        total = sum(clipped)
        scores = [x / total for x in clipped] if total > 0 else [1.0 / len(clipped)] * len(clipped)
    elif request.eeg_score_type == EEGScoreType.normalized_evidence:
        clipped = [max(0.0, min(1.0, x)) for x in raw]
        if max(clipped, default=0.0) == 0:
            scores = [1.0 / len(clipped)] * len(clipped)
        else:
            maxv = max(clipped)
            scores = [x / maxv for x in clipped]
    else:
        # Correlation / decision scores are not probabilities; softmax creates a bounded ranking weight only.
        scores = _softmax(raw, settings.eeg_softmax_temperature)

    pairs = list(zip([h.initials for h in hyps], scores, strict=True))
    pairs.sort(key=lambda x: x[1], reverse=True)
    return pairs
