from __future__ import annotations

from fastapi import HTTPException

from app.korean.initials import (
    extract_initials,
    extract_units,
    normalize_initials,
    normalize_text,
    validate_initials,
)
from app.schemas import PredictionRequest


def normalize_request(request: PredictionRequest) -> PredictionRequest:
    request = request.model_copy(deep=True)

    if request.input_mode.value == "initials":
        normalized = normalize_initials(request.bci_input)
        if not validate_initials(normalized):
            raise HTTPException(
                status_code=422,
                detail="initials mode에서는 한글 초성(ㄱ~ㅎ)만 입력할 수 있습니다.",
            )
        request.bci_input = normalized

    if request.eeg_hypotheses:
        cleaned = []
        for h in request.eeg_hypotheses:
            initials = normalize_initials(h.initials)
            if validate_initials(initials):
                cleaned.append(h.model_copy(update={"initials": initials}))
        request.eeg_hypotheses = cleaned or None

    # ------------------------------------------------------------------
    # KeywordAE (spelled_syllables): every pinned position must fall inside
    # the current initials string, and the syllable the user actually spelled
    # must itself start with the initial consonant the user originally chose
    # for that position -- otherwise the "recovery" would silently contradict
    # what the person already committed to on the initials keyboard.
    # ------------------------------------------------------------------
    if request.spelled_syllables:
        bci_len = len(request.bci_input)
        cleaned_spelled: dict[int, str] = {}
        for index, syllable in request.spelled_syllables.items():
            syllable = normalize_text(syllable)
            if not syllable or index >= bci_len:
                raise HTTPException(status_code=422, detail="고정 글자의 위치가 초성열 범위를 벗어났습니다.")
            expected_initial = request.bci_input[index]
            if extract_initials(syllable) != expected_initial:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"{index}번째 글자의 초성은 '{expected_initial}'이어야 합니다 "
                        f"(입력된 글자: '{syllable}')."
                    ),
                )
            cleaned_spelled[index] = syllable
        request.spelled_syllables = cleaned_spelled or None

    # ------------------------------------------------------------------
    # FillMask: the reference candidate must have the same number of
    # syllable/jamo units as the current initials string (it was, after
    # all, generated to match it), and the target index must fall inside it.
    # ------------------------------------------------------------------
    if request.fill_mask_reference_text is not None and request.fill_mask_target_index is not None:
        ref_units = extract_units(request.fill_mask_reference_text)
        if (extract_initials(request.fill_mask_reference_text) != request.bci_input
                or request.fill_mask_target_index >= len(ref_units)):
            raise HTTPException(
                status_code=422,
                detail="fill_mask_reference_text가 현재 초성열 길이와 맞지 않습니다.",
            )

    return request
