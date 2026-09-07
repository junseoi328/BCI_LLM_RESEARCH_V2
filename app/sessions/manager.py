from __future__ import annotations

import threading
import uuid

from app.schemas import Partner, RankedCandidate, SessionState, Situation


class InMemorySessionManager:
    """Research-prototype session store.

    This is intentionally in-memory. Replace with Redis/DB before multi-worker or production use.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, SessionState] = {}

    def start(self, partner: Partner, situation: Situation) -> SessionState:
        session = SessionState(
            session_id=f"s_{uuid.uuid4().hex[:12]}",
            partner=partner,
            situation=situation,
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session.model_copy(deep=True)

    def get(self, session_id: str) -> SessionState | None:
        with self._lock:
            value = self._sessions.get(session_id)
            return value.model_copy(deep=True) if value else None

    def set_candidates(self, session_id: str, candidates: list[RankedCandidate]) -> SessionState:
        with self._lock:
            s = self._sessions[session_id]
            s.last_candidates = [c.model_copy(deep=True) for c in candidates]
            return s.model_copy(deep=True)

    def select(self, session_id: str, candidate_id: str) -> SessionState:
        with self._lock:
            s = self._sessions[session_id]
            candidate = next((c for c in s.last_candidates if c.candidate_id == candidate_id), None)
            if candidate is None:
                raise KeyError("candidate_not_found")
            if s.sentence and not s.sentence.endswith(" "):
                s.sentence += " "
            s.sentence += candidate.text
            s.history.append(candidate.text)
            s.last_candidates = []
            return s.model_copy(deep=True)

    def append_text(self, session_id: str, text: str) -> SessionState:
        """Same buffer/history bookkeeping as select(), but for free text that
        did not come from a /predict candidate (e.g. a habitual-phrase
        quick-chip). Also clears last_candidates, matching select()'s
        contract that a commit ends the current candidate round."""
        text = text.strip()
        with self._lock:
            s = self._sessions[session_id]
            if not text:
                return s.model_copy(deep=True)
            if s.sentence and not s.sentence.endswith(" "):
                s.sentence += " "
            s.sentence += text
            s.history.append(text)
            s.last_candidates = []
            return s.model_copy(deep=True)

    def undo(self, session_id: str) -> tuple[SessionState, str | None]:
        with self._lock:
            s = self._sessions[session_id]
            undone = s.history.pop() if s.history else None
            if undone:
                parts = s.sentence.split()
                n = len(undone.split())
                s.sentence = " ".join(parts[:-n]) if n <= len(parts) else ""
            s.last_candidates = []
            return s.model_copy(deep=True), undone

    def reset(self, session_id: str) -> SessionState:
        with self._lock:
            s = self._sessions[session_id]
            s.sentence = ""
            s.history = []
            s.last_candidates = []
            return s.model_copy(deep=True)


session_manager = InMemorySessionManager()
