from __future__ import annotations

from fastapi import HTTPException

from app.korean.initials import normalize_initials, validate_initials
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

    return request
