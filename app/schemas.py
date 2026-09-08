from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator


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
    score: float = Field(allow_inf_nan=False)


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
    eeg_hypotheses: list[EEGHypothesis] | None = Field(default=None, max_length=20)
    eeg_score_type: EEGScoreType = EEGScoreType.normalized_evidence
    top_k: int = Field(default=3, ge=1, le=5)

    # ------------------------------------------------------------------
    # Recovery interactions (SpeakFaster KeywordAE / FillMask, see
    # app/pipeline/recovery.py for the pipeline-side handling).
    #
    # KeywordAE: the user has directly spelled out one or more syllable
    # positions (via the Auto Toggle jamo keyboard) because none of the
    # initials-only Top-K candidates were the intended phrase. Keys are
    # 0-indexed positions aligned with app.korean.initials.extract_units(),
    # values are the exact composed syllable text for that position.
    #
    # FillMask: the user picked a candidate that was almost right (one
    # wrong syllable/word) and wants alternatives for just that position.
    # fill_mask_reference_text is the almost-right candidate text,
    # fill_mask_target_index is the position (same indexing) to vary.
    #
    # Only one of the two recovery modes is meaningful per request; if both
    # are provided KeywordAE takes priority (it is the team's stated
    # priority: "KeywordAE >> FillMask").
    # ------------------------------------------------------------------
    spelled_syllables: dict[int, str] | None = Field(default=None, max_length=20)
    fill_mask_reference_text: str | None = Field(default=None, max_length=80)
    fill_mask_target_index: int | None = Field(default=None, ge=0)

    @field_validator("recent_context")
    @classmethod
    def validate_context_items(cls, values: list[str]) -> list[str]:
        return [v.strip()[:300] for v in values if v and v.strip()]

    @field_validator("spelled_syllables")
    @classmethod
    def validate_spelled_syllables(cls, value: dict[int, str] | None) -> dict[int, str] | None:
        if not value:
            return None
        cleaned: dict[int, str] = {}
        for index, text in value.items():
            text = str(text).strip()
            if not text or index < 0:
                continue
            cleaned[int(index)] = text[:4]
        return cleaned or None

    @model_validator(mode="after")
    def validate_recovery_shape(self) -> "PredictionRequest":
        if self.fill_mask_target_index is not None and not self.fill_mask_reference_text:
            raise ValueError("fill_mask_target_index를 사용하려면 fill_mask_reference_text가 필요합니다.")
        if self.fill_mask_reference_text and self.fill_mask_target_index is None:
            raise ValueError("fill_mask_reference_text를 사용하려면 fill_mask_target_index가 필요합니다.")
        return self


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
    recovery_mode: str = "none"
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


class HabitualPhrase(BaseModel):
    text: str
    count: int


class HabitualPhraseResponse(BaseModel):
    phrases: list[HabitualPhrase]
