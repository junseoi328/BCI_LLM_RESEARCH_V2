from app.korean.composer import compose_syllable
from app.pipeline.autotoggle import step
from app.schemas import AutoToggleState, AutoToggleStepRequest


def test_compose():
    assert compose_syllable("ㄷ", "ㅗ") == "도"
    assert compose_syllable("ㅁ", "ㅜ", "ㄹ") == "물"


def test_autotoggle_commit():
    state = AutoToggleState()
    r1 = step(AutoToggleStepRequest(state=state, action="input", jamo="ㄷ"))
    r2 = step(AutoToggleStepRequest(state=r1.state, action="input", jamo="ㅗ"))
    assert r2.preview == "도"
    r3 = step(AutoToggleStepRequest(state=r2.state, action="commit"))
    assert r3.state.committed_text == "도"


def test_autotoggle_backspace():
    state = AutoToggleState(initial="ㄷ", medial="ㅗ")
    r = step(AutoToggleStepRequest(state=state, action="backspace"))
    assert r.state.medial is None
