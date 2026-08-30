from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator


class InputMode(str, Enum):
    initials = "initials"
    jamo = "jamo"


class ExperimentMode(str, Enum):
    baseline_autotoggle = "baseline_autotoggle"
    autotoggle_llm = "autotoggle_llm"
    initials_llm = "initials_llm"
    hybrid = "hybrid"


class ContextLevel(str, Enum):
    none = "none"
    partner = "partner"
    partner_situation = "partner_situation"
    full = "full"


class Partner(str, Enum):
    family = "family"
    friend = "friend"
    caregiver = "caregiver"
    medical_staff = "medical_staff"
    other = "other"


class Situation(str, Enum):
    general = "general"
    home = "home"
    hospital = "hospital"
    meal = "meal"
    pain = "pain"
    positioning = "positioning"
    schedule = "schedule"
    entertainment = "entertainment"
    emergency = "emergency"


class EEGScoreType(str, Enum):
    probability = "probability"
    normalized_evidence = "normalized_evidence"
    correlation = "correlation"
    decision_score = "decision_score"


class EEGHypothesis(BaseModel):
    initials: str = Field(min_length=1, max_length=20)
    score: float


class PredictionRequest(BaseModel):
    session_id: str | None = Field(default=None, max_length=80)
    trial_id: str | None = Field(default=None, max_length=80)
    experiment_mode: ExperimentMode = ExperimentMode.initials_llm
    input_mode: InputMode = InputMode.initials
    bci_input: str = Field(min_length=1, max_length=20)
    partner: Partner = Partner.other
    situation: Situation = Situation.general
    current_sentence: str = Field(default="", max_length=300)
    recent_context: list[str] = Field(default_factory=list, max_length=5)
    context_level: ContextLevel = ContextLevel.full
    eeg_hypotheses: list[EEGHypothesis] | None = None
    eeg_score_type: EEGScoreType = EEGScoreType.normalized_evidence
    top_k: int = Field(default=3, ge=1, le=5)

    @field_validator("recent_context")
    @classmethod
    def validate_context_items(cls, values: list[str]) -> list[str]:
        return [v.strip()[:300] for v in values if v and v.strip()]


class GeneratedCandidate(BaseModel):
    candidate_id: str
    text: str = Field(min_length=1, max_length=80)
    source_initials: str
    generation_order: int = Field(ge=1)
    eeg_score: float | None = Field(default=None, ge=0.0, le=1.0)


class RankedCandidate(BaseModel):
    candidate_id: str
    text: str
    rank: int
    matched_initials: str
    eeg_score: float | None = Field(default=None, ge=0.0, le=1.0)
    context_score: float = Field(ge=0.0, le=1.0)
    intent_score: float = Field(ge=0.0, le=1.0)
    naturalness_score: float = Field(ge=0.0, le=1.0)
    partner_score: float = Field(ge=0.0, le=1.0)
    language_score: float = Field(ge=0.0, le=1.0)
    final_score: float = Field(ge=0.0, le=1.0)


class LatencyBreakdown(BaseModel):
    generation_ms: int = 0
    ranking_ms: int = 0
    postprocess_ms: int = 0
    total_ms: int = 0


class UsageSummary(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float | None = None


class PredictionResponse(BaseModel):
    request_id: str
    candidates: list[RankedCandidate]
    fallback: str = "none"
    hybrid_action: str = "show_candidates"
    latency: LatencyBreakdown
    generator_model: str
    ranker_model: str
    usage: UsageSummary
    pipeline_version: str
    generator_prompt_version: str
    ranker_prompt_version: str
    warnings: list[str] = Field(default_factory=list)
    debug: dict[str, Any] | None = None


class AutoToggleState(BaseModel):
    committed_text: str = ""
    initial: str | None = None
    medial: str | None = None
    final: str | None = None


class AutoToggleStepRequest(BaseModel):
    state: AutoToggleState = Field(default_factory=AutoToggleState)
    action: str = Field(description="input | commit | backspace | reset")
    jamo: str | None = None


class AutoToggleStepResponse(BaseModel):
    state: AutoToggleState
    preview: str
    status: str


class SessionStartRequest(BaseModel):
    partner: Partner = Partner.other
    situation: Situation = Situation.general


class SessionState(BaseModel):
    session_id: str
    partner: Partner
    situation: Situation
    sentence: str = ""
    history: list[str] = Field(default_factory=list)
    last_candidates: list[RankedCandidate] = Field(default_factory=list)


class SessionSelectRequest(BaseModel):
    candidate_id: str


class SessionUndoResponse(BaseModel):
    session: SessionState
    undone: str | None = None
