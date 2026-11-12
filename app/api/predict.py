from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.errors import LLMServiceError
from app.pipeline.service import BCILanguagePipeline
from app.schemas import PredictionRequest, PredictionResponse

router = APIRouter()
pipeline = BCILanguagePipeline()


@router.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest) -> PredictionResponse:
    try:
        return pipeline.predict(request)
    except HTTPException:
        raise
    except LLMServiceError as exc:
        detail = {"code": exc.code, "message": exc.message, "retryable": exc.retryable}
        raise HTTPException(status_code=503, detail=detail) from exc
    except Exception as exc:
        if settings.debug_mode:
            detail = {"code": type(exc).__name__, "message": str(exc)[:500]}
        else:
            detail = {"code": "internal_error", "message": "prediction service unavailable"}
        raise HTTPException(status_code=503, detail=detail) from exc


class ReplyWordsRequest(BaseModel):
    partner_text: str = Field(min_length=1, max_length=300)
    partner: str = Field(default="other", max_length=30)
    situation: str = Field(default="general", max_length=30)
    recent: list[str] = Field(default_factory=list, max_length=5)
    news: str = Field(default="", max_length=300)


_REPLY_WORD = re.compile(r"^[가-힣]{1,10}$")


@router.post("/reply-words")
def reply_words(request: ReplyWordsRequest) -> dict:
    """상대 말에 답할 단어 추천. 실패하면 빈 목록 — 로컬 후보가 계속 동작한다."""
    client = pipeline.model_client
    fn = next((getattr(c, "generate_reply_words") for c in (client, getattr(client, "live", None),
               getattr(client, "base", None), getattr(client, "cloud_ranker", None))
               if c is not None and hasattr(c, "generate_reply_words")), None)
    if fn is None:
        return {"words": []}
    try:
        raw = fn(request.partner_text, request.partner, request.situation, [r[:200] for r in request.recent], request.news)
    except LLMServiceError:
        return {"words": []}
    words = list(dict.fromkeys(w for w in raw if _REPLY_WORD.match(w)))
    return {"words": words[:30]}
