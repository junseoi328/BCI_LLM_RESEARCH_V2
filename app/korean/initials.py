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
