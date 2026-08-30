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
    for candidate in candidates:
        if any(text_similarity(candidate.text, existing.text) >= settings.diversity_similarity_threshold for existing in kept):
            continue
        kept.append(candidate)
    return kept
