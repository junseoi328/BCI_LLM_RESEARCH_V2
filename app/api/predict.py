from __future__ import annotations

from fastapi import APIRouter, HTTPException

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
