from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.predict import pipeline
from app.llm.habitual_store import habitual_store
from app.schemas import (
    HabitualPhraseResponse,
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


@router.get("/{session_id}/habitual", response_model=HabitualPhraseResponse)
def habitual_phrases(session_id: str, limit: int = 6) -> HabitualPhraseResponse:
    """익숙하게 쓰는 문장: phrases this person (in this partner/situation
    context, falling back to broader context) has committed most often
    across sessions, so they can be offered as an instant one-tap shortcut
    that skips generation entirely."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    limit = max(1, min(limit, 12))
    ranked = habitual_store.top_tiered(
        partner=session.partner.value,
        situation=session.situation.value,
        limit=limit,
    )
    return HabitualPhraseResponse(
        phrases=[{"text": text, "count": count} for text, count in ranked]
    )


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
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    committed = next(
        (c for c in session.last_candidates if c.candidate_id == request.candidate_id),
        None,
    )
    try:
        updated = session_manager.select(session_id, request.candidate_id)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail="candidate_id is not in the latest candidate list") from exc
    if committed is not None:
        habitual_store.record(session.partner.value, session.situation.value, committed.text)
    return updated


@router.post("/{session_id}/select_text", response_model=SessionState)
def select_text(session_id: str, request: dict) -> SessionState:
    """Directly commit an arbitrary phrase (bypassing candidate_id lookup).

    Used by the habitual-phrase quick-chips: those phrases were never part
    of a /predict response and therefore have no candidate_id to select, so
    the frontend needs a way to commit free text straight into the session
    the same way a normal Top-K selection would (buffer, history, and the
    habitual store all stay consistent either way)."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    text = str(request.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is required")
    updated = session_manager.append_text(session_id, text)
    habitual_store.record(session.partner.value, session.situation.value, text)
    return updated


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
