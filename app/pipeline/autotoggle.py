from __future__ import annotations

from app.korean.composer import CHO_SET, JUNG_SET, JONG_SET, compose_syllable
from app.schemas import AutoToggleState, AutoToggleStepRequest, AutoToggleStepResponse


def preview(state: AutoToggleState) -> str:
    pending = ""
    if state.initial and state.medial:
        pending = compose_syllable(state.initial, state.medial, state.final)
    elif state.initial:
        pending = state.initial
    return state.committed_text + pending


def step(req: AutoToggleStepRequest) -> AutoToggleStepResponse:
    s = req.state.model_copy(deep=True)
    action = req.action.lower().strip()

    if action == "reset":
        s = AutoToggleState()
        return AutoToggleStepResponse(state=s, preview="", status="reset")

    if action == "backspace":
        if s.final:
            s.final = None
        elif s.medial:
            s.medial = None
        elif s.initial:
            s.initial = None
        elif s.committed_text:
            s.committed_text = s.committed_text[:-1]
        return AutoToggleStepResponse(state=s, preview=preview(s), status="edited")

    if action == "commit":
        if s.initial and s.medial:
            s.committed_text += compose_syllable(s.initial, s.medial, s.final)
            s.initial = s.medial = s.final = None
            return AutoToggleStepResponse(state=s, preview=s.committed_text, status="committed")
        return AutoToggleStepResponse(state=s, preview=preview(s), status="nothing_to_commit")

    if action != "input" or not req.jamo:
        raise ValueError("action은 input/commit/backspace/reset 중 하나이며 input에는 jamo가 필요합니다.")

    j = req.jamo
    if j in CHO_SET and s.initial is None:
        s.initial = j
        status = "initial_selected"
    elif j in JUNG_SET and s.initial and s.medial is None:
        s.medial = j
        status = "syllable_ready"
    elif j in JONG_SET and s.initial and s.medial and s.final is None:
        s.final = j
        status = "final_selected"
    elif j in CHO_SET and s.initial and s.medial:
        # New consonant starts a new syllable: commit current pending syllable first.
        s.committed_text += compose_syllable(s.initial, s.medial, s.final)
        s.initial, s.medial, s.final = j, None, None
        status = "auto_committed_and_new_initial"
    else:
        raise ValueError("현재 state에서 해당 자모를 입력할 수 없습니다.")

    return AutoToggleStepResponse(state=s, preview=preview(s), status=status)
