from __future__ import annotations

import re
import unicodedata

CHOSEONG = [
    "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ",
    "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
]
CHOSEONG_SET = set(CHOSEONG)
HANGUL_BASE = ord("가")
HANGUL_END = ord("힣")
SYLLABLES_PER_INITIAL = 21 * 28  # 588


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFC", text or "").strip()


def normalize_initials(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "")
    text = re.sub(r"\s+", "", text)
    return text


def validate_initials(initials: str) -> bool:
    initials = normalize_initials(initials)
    return bool(initials) and all(ch in CHOSEONG_SET for ch in initials)


def extract_initials(text: str, *, ignore_spaces: bool = True) -> str:
    text = normalize_text(text)
    result: list[str] = []
    for ch in text:
        code = ord(ch)
        if HANGUL_BASE <= code <= HANGUL_END:
            index = (code - HANGUL_BASE) // SYLLABLES_PER_INITIAL
            result.append(CHOSEONG[index])
        elif ch in CHOSEONG_SET:
            result.append(ch)
        elif ch.isspace() and ignore_spaces:
            continue
        # punctuation / latin / digits are ignored for initial matching
    return "".join(result)


def exact_initial_match(text: str, initials: str) -> bool:
    return extract_initials(text) == normalize_initials(initials)


def prefix_initial_match(text: str, initials: str) -> bool:
    return extract_initials(text).startswith(normalize_initials(initials))


# ---------------------------------------------------------------------------
# KeywordAE / FillMask recovery support (SpeakFaster-style partial-spelling
# and near-miss word-swap recovery, adapted to Korean initials-based input).
#
# extract_initials() walks a string and, for every Hangul syllable or bare
# choseong character it finds (skipping whitespace), emits one *initial
# consonant*. extract_units() below walks the exact same characters in the
# exact same order/positions but emits the *whole unit* (the full syllable
# character itself, or the bare choseong jamo) instead of just its initial.
# This keeps position i of extract_units(text) aligned 1:1 with position i
# of extract_initials(text), which is what lets a recovery request pin down
# "position i must be exactly this syllable" or "position i must differ
# between two texts while every other position stays identical".
# ---------------------------------------------------------------------------


def extract_units(text: str, *, ignore_spaces: bool = True) -> list[str]:
    text = normalize_text(text)
    result: list[str] = []
    for ch in text:
        code = ord(ch)
        if HANGUL_BASE <= code <= HANGUL_END:
            result.append(ch)
        elif ch in CHOSEONG_SET:
            result.append(ch)
        elif ch.isspace() and ignore_spaces:
            continue
    return result


def spelled_constraint_match(text: str, spelled: dict[int, str] | None) -> bool:
    """KeywordAE check: every pinned position must match the given syllable exactly."""
    if not spelled:
        return True
    units = extract_units(text)
    for index, value in spelled.items():
        value = normalize_text(value)
        if index < 0 or index >= len(units):
            return False
        if units[index] != value:
            return False
    return True


def fill_mask_constraint_match(text: str, reference_text: str, target_index: int) -> bool:
    """FillMask check: identical to reference at every position except target_index,
    and target_index must actually be different (otherwise it is not an alternative)."""
    units = extract_units(text)
    ref_units = extract_units(reference_text)
    if len(units) != len(ref_units):
        return False
    if target_index < 0 or target_index >= len(units):
        return False
    for i, (a, b) in enumerate(zip(units, ref_units, strict=True)):
        if i == target_index:
            continue
        if a != b:
            return False
    return units[target_index] != ref_units[target_index]
