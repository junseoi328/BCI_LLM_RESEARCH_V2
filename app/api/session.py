from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.predict import pipeline
from app.schemas import (
    PredictionRequest,
    PredictionResponse,
    SessionSelectRequest,
    SessionStartRequest,
    SessionState,
    SessionUndoResponse,
)
from app.sessions.manager import session_manager

router = APIRouter(prefix="/session")


@router.post("/start", response_model=SessionState)
def start_session(request: SessionStartRequest) -> SessionState:
    return session_manager.start(request.partner, request.situation)


@router.get("/{session_id}", response_model=SessionState)
def get_session(session_id: str) -> SessionState:
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    return session


@router.post("/{session_id}/predict", response_model=PredictionResponse)
def session_predict(session_id: str, request: PredictionRequest) -> PredictionResponse:
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    patched = request.model_copy(
        update={
            "session_id": session_id,
            "partner": session.partner,
            "situation": session.situation,
            "current_sentence": session.sentence,
            "recent_context": session.history[-5:],
        }
    )
    response = pipeline.predict(patched)
    session_manager.set_candidates(session_id, response.candidates)
    return response


@router.post("/{session_id}/select", response_model=SessionState)
def select_candidate(session_id: str, request: SessionSelectRequest) -> SessionState:
    if not session_manager.get(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    try:
        return session_manager.select(session_id, request.candidate_id)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail="candidate_id is not in the latest candidate list") from exc


@router.post("/{session_id}/undo", response_model=SessionUndoResponse)
def undo(session_id: str) -> SessionUndoResponse:
    if not session_manager.get(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    session, undone = session_manager.undo(session_id)
    return SessionUndoResponse(session=session, undone=undone)


@router.post("/{session_id}/reset", response_model=SessionState)
def reset(session_id: str) -> SessionState:
    if not session_manager.get(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return session_manager.reset(session_id)
