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


class ChooseRequest(BaseModel):
    slots: list[list[str]] = Field(min_length=2, max_length=12)
    recent_context: list[str] = Field(default_factory=list, max_length=6)
    current_sentence: str = Field(default="", max_length=300)


_CHOOSE_WORD = re.compile(r"^[가-힣?!.,~]{1,12}$")


@router.post("/choose")
def choose(request: ChooseRequest) -> dict:
    """로컬 격자(어절마다 초성이 맞는 단어 목록)에서 LLM이 고른 문장. 실패하면 빈 목록 — 로컬 후보는 그대로."""
    slots = [[w for w in ws if _CHOOSE_WORD.match(w)][:20] for ws in request.slots]
    if any(not ws for ws in slots):
        return {"candidates": []}
    client = pipeline.model_client
    fn = next((getattr(c, "choose_sentences") for c in (client, getattr(client, "live", None),
               getattr(client, "base", None), getattr(client, "cloud_ranker", None))
               if c is not None and hasattr(c, "choose_sentences")), None)
    if fn is None:   # 모의 모드: 각 어절의 1번(로컬 최상위)
        picks_list = [[0] * len(slots)]
    else:
        ctx = "\n".join(r[:200] for r in request.recent_context[-5:])
        if request.current_sentence:
            ctx += f"\n지금까지 쓴 말: {request.current_sentence[-200:]}"
        try:
            picks_list = fn(slots, ctx.strip())
        except LLMServiceError:
            return {"candidates": []}
    out = []
    for picks in picks_list:
        if len(picks) != len(slots) or not all(isinstance(i, int) and 0 <= i < len(ws) for i, ws in zip(picks, slots)):
            continue                                  # 목록 밖 번호는 버린다 — 초성 일치를 코드가 보장
        text = " ".join(ws[i] for i, ws in zip(picks, slots))
        if text not in (c["text"] for c in out):
            out.append({"candidate_id": f"ch{len(out)+1}", "text": text, "rank": len(out) + 1})
    return {"candidates": out[:3], "source": "lattice"}


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
