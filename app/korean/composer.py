from __future__ import annotations

CHO = ["ㄱ","ㄲ","ㄴ","ㄷ","ㄸ","ㄹ","ㅁ","ㅂ","ㅃ","ㅅ","ㅆ","ㅇ","ㅈ","ㅉ","ㅊ","ㅋ","ㅌ","ㅍ","ㅎ"]
JUNG = ["ㅏ","ㅐ","ㅑ","ㅒ","ㅓ","ㅔ","ㅕ","ㅖ","ㅗ","ㅘ","ㅙ","ㅚ","ㅛ","ㅜ","ㅝ","ㅞ","ㅟ","ㅠ","ㅡ","ㅢ","ㅣ"]
JONG = ["", "ㄱ","ㄲ","ㄳ","ㄴ","ㄵ","ㄶ","ㄷ","ㄹ","ㄺ","ㄻ","ㄼ","ㄽ","ㄾ","ㄿ","ㅀ","ㅁ","ㅂ","ㅄ","ㅅ","ㅆ","ㅇ","ㅈ","ㅊ","ㅋ","ㅌ","ㅍ","ㅎ"]

CHO_SET, JUNG_SET, JONG_SET = set(CHO), set(JUNG), set(JONG[1:])


def compose_syllable(initial: str, medial: str, final: str | None = None) -> str:
    if initial not in CHO_SET or medial not in JUNG_SET:
        raise ValueError("유효하지 않은 초성/중성입니다.")
    final = final or ""
    if final not in JONG:
        raise ValueError("유효하지 않은 종성입니다.")
    code = 0xAC00 + (CHO.index(initial) * 21 + JUNG.index(medial)) * 28 + JONG.index(final)
    return chr(code)
