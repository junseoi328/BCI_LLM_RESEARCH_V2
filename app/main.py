from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.autotoggle import router as autotoggle_router
from app.api.predict import router as predict_router
from app.api.session import router as session_router
from app.config import ROOT_DIR, settings

app = FastAPI(
    title="BCI Korean Language Prediction API",
    version=settings.pipeline_version,
    description="P300/EEG partial Korean input + conversation context -> ranked Korean communication candidates",
)

origins = ["*"] if settings.app_env == "development" and settings.debug_mode else settings.allowed_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(predict_router, tags=["prediction"])
app.include_router(autotoggle_router, tags=["auto-toggle"])
app.include_router(session_router, tags=["session"])


@app.get("/")
def root():
    return {
        "service": "bci-korean-language-api",
        "status": "ok",
        "version": settings.pipeline_version,
        "mock_mode": settings.mock_mode,
        "generator_model": "mock" if settings.mock_mode else settings.generator_model,
        "ranker_model": "mock" if settings.mock_mode else settings.ranker_model,
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "mock_mode": settings.mock_mode,
        "pipeline_version": settings.pipeline_version,
    }


@app.get("/demo", include_in_schema=False)
def demo():
    path = ROOT_DIR / "static" / "demo.html"
    return FileResponse(path)
