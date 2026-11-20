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


def _cho(word: str) -> str:
    return "".join("ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"[(ord(c) - 0xAC00) // 588] for c in word if "가" <= c <= "힣")


@router.post("/choose")
def choose(request: ChooseRequest) -> dict:
    """어절마다 초성 + 로컬 후보 목록(힌트)으로 문장을 해독한다. 어절 수·어절별 초성이 정확히 맞는 문장만 낸다.
    실패하면 빈 목록 — 로컬 후보는 그대로 동작한다."""
    slots = [[w for w in ws if _CHOOSE_WORD.match(w)][:20] for ws in request.slots]
    if any(not ws for ws in slots):
        return {"candidates": []}
    initials = [_cho(ws[0]) for ws in slots]
    if any(not ini or any(_cho(w) != ini for w in ws) for ini, ws in zip(initials, slots)):
        return {"candidates": []}                       # 한 어절 안의 후보는 초성이 모두 같아야 한다
    client = pipeline.model_client
    fn = next((getattr(c, "choose_sentences") for c in (client, getattr(client, "live", None),
               getattr(client, "base", None), getattr(client, "cloud_ranker", None))
               if c is not None and hasattr(c, "choose_sentences")), None)
    model = "local"
    if fn is None:   # 모의 모드: 각 어절의 1번(로컬 최상위)
        texts = [" ".join(ws[0] for ws in slots)]
    else:
        ctx = "\n".join(r[:200] for r in request.recent_context[-5:])
        if request.current_sentence:
            ctx += f"\n지금까지 쓴 말: {request.current_sentence[-200:]}"
        try:
            texts, model = fn(slots, ctx.strip(), initials)
        except LLMServiceError:
            return {"candidates": []}
    out = []
    for text in texts:
        words = re.sub(r"[^가-힣\s]", "", str(text)).split()
        if [_cho(w) for w in words] != initials or any(len(w) != len(i) for w, i in zip(words, initials)):
            continue                                  # 어절 수·초성이 하나라도 다르면 버린다
        t = " ".join(words)
        if t not in (c["text"] for c in out):
            out.append({"candidate_id": f"ch{len(out)+1}", "text": t, "rank": len(out) + 1})
    return {"candidates": out[:3], "source": "decode", "model": model}


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
