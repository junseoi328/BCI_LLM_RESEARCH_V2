from app.korean.initials import extract_initials, exact_initial_match, normalize_initials, validate_initials


def test_extract_initials():
    assert extract_initials("도와줘") == "ㄷㅇㅈ"
    assert extract_initials("물 줘") == "ㅁㅈ"
    assert extract_initials("자세 바꿔줘") == "ㅈㅅㅂㄲㅈ"


def test_normalize_and_validate():
    assert normalize_initials(" ㄷ ㅇ ㅈ ") == "ㄷㅇㅈ"
    assert validate_initials("ㄷㅇㅈ")
    assert not validate_initials("도와줘")


def test_exact_match():
    assert exact_initial_match("다음 주", "ㄷㅇㅈ")
    assert not exact_initial_match("도와주세요", "ㄷㅇㅈ")
