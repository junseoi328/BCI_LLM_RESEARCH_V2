from __future__ import annotations

from difflib import SequenceMatcher

from app.config import settings
from app.pipeline.filter import canonicalize
from app.schemas import GeneratedCandidate


def text_similarity(a: str, b: str) -> float:
    a2, b2 = canonicalize(a), canonicalize(b)
    if not a2 or not b2:
        return 0.0
    return SequenceMatcher(None, a2, b2).ratio()


def remove_near_duplicates(candidates: list[GeneratedCandidate]) -> list[GeneratedCandidate]:
    kept: list[GeneratedCandidate] = []
    kept_texts: list[str] = []
    threshold = settings.diversity_similarity_threshold
    for candidate in candidates:
        normalized = canonicalize(candidate.text)
        if any(
            (SequenceMatcher(None, normalized, existing).ratio()
             if normalized and existing else 0.0) >= threshold
            for existing in kept_texts
        ):
            continue
        kept.append(candidate)
        kept_texts.append(normalized)
    return kept
