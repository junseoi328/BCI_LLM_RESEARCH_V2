from __future__ import annotations

import re
from collections.abc import Iterable

from app.korean.initials import exact_initial_match, spelled_constraint_match
from app.schemas import GeneratedCandidate


def canonicalize(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE).lower()


def filter_candidates(
    candidates: Iterable[GeneratedCandidate],
    initials: str,
    spelled: dict[int, str] | None = None,
) -> list[GeneratedCandidate]:
    result: list[GeneratedCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        text = candidate.text.strip()
        key = canonicalize(text)
        if not text or not key or key in seen:
            continue
        if not exact_initial_match(text, initials):
            continue
        if spelled and not spelled_constraint_match(text, spelled):
            continue
        seen.add(key)
        result.append(candidate.model_copy(update={"text": text}))
    return result
