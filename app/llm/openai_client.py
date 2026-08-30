from __future__ import annotations

import json

from app.config import settings
from app.errors import LLMServiceError
from app.llm.prompts import (
    GENERATOR_INSTRUCTIONS,
    RANKER_INSTRUCTIONS,
    build_generator_input,
    build_ranker_input,
)
from app.llm.types import CandidateScore, GenerationCallResult, RankingCallResult, TokenUsage
from app.schemas import GeneratedCandidate


def _parse_structured_json_response(response, stage: str) -> dict:
    """Parse Responses API Structured Output without crashing on incomplete output.

    Structured Outputs guarantees schema adherence for a completed response, but a
    response can still be incomplete (for example when max_output_tokens is hit).
    In that case response.output_text can contain truncated JSON.
    """
    status = getattr(response, "status", None)
    if status and status != "completed":
        details = getattr(response, "incomplete_details", None)
        reason = getattr(details, "reason", None) if details is not None else None
        if reason == "max_output_tokens":
            raise LLMServiceError(
                "incomplete_max_output_tokens",
                f"{stage} 응답이 max_output_tokens 한도에서 잘렸습니다.",
                retryable=True,
            )
        raise LLMServiceError(
            "incomplete_response",
            f"{stage} 응답이 완료되지 않았습니다(status={status}, reason={reason}).",
            retryable=True,
        )

    text = (getattr(response, "output_text", "") or "").strip()
    if not text:
        raise LLMServiceError(
            "empty_structured_output",
            f"{stage} Structured Output이 비어 있습니다.",
            retryable=True,
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        # Do not leak raw model/user text in the exception message.
        raise LLMServiceError(
            "malformed_structured_output",
            f"{stage} Structured Output JSON이 완전하지 않습니다.",
            retryable=True,
        ) from exc


class OpenAILanguageModelClient:
    def __init__(self, generator_model: str | None = None, ranker_model: str | None = None):
        if not settings.openai_api_key:
            raise LLMServiceError("missing_api_key", "OPENAI_API_KEY가 설정되지 않았습니다.")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMServiceError("sdk_missing", "openai 패키지가 설치되지 않았습니다.") from exc

        self.generator_model_name = generator_model or settings.generator_model
        self.ranker_model_name = ranker_model or settings.ranker_model
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout_sec,
            max_retries=settings.openai_max_retries,
        )

    @staticmethod
    def _usage(response) -> TokenUsage:
        usage = getattr(response, "usage", None)
        if usage is None:
            return TokenUsage()
        return TokenUsage(
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        )

    @staticmethod
    def _raise_clean_error(exc: Exception) -> None:
        name = type(exc).__name__
        message = str(exc)
        if name == "AuthenticationError":
            raise LLMServiceError("authentication_error", "OpenAI API 인증에 실패했습니다.") from exc
        if name == "RateLimitError":
            lower = message.lower()
            if "project_spend_limit" in lower:
                code = "project_spend_limit_exceeded"
                text = "OpenAI project spend limit에 도달했습니다."
            elif "organization" in lower and "limit" in lower:
                code = "organization_limit_exceeded"
                text = "OpenAI organization usage/spend limit에 도달했습니다."
            elif "insufficient_quota" in lower or "credit_balance" in lower or "quota" in lower:
                code = "insufficient_quota"
                text = "OpenAI API credit/quota가 부족합니다."
            else:
                code = "rate_limit"
                text = "OpenAI API rate limit에 도달했습니다."
            raise LLMServiceError(code, text, retryable=True) from exc
        if name in {"APITimeoutError", "TimeoutError"}:
            raise LLMServiceError("timeout", "OpenAI API 응답 시간이 초과되었습니다.", retryable=True) from exc
        if name == "APIConnectionError":
            raise LLMServiceError("connection_error", "OpenAI API 연결에 실패했습니다.", retryable=True) from exc
        if name == "BadRequestError":
            raise LLMServiceError("bad_request", f"OpenAI 요청 형식 오류: {message[:300]}") from exc
        raise LLMServiceError("openai_error", f"OpenAI API 오류: {name}") from exc

    @staticmethod
    def _generator_schema() -> dict:
        return {
            "type": "object",
            "properties": {
                "candidates": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            },
            "required": ["candidates"],
            "additionalProperties": False,
        }

    @staticmethod
    def _ranker_schema() -> dict:
        item = {
            "type": "object",
            "properties": {
                "candidate_id": {"type": "string"},
                "context_score": {"type": "number", "minimum": 0, "maximum": 1},
                "intent_score": {"type": "number", "minimum": 0, "maximum": 1},
                "naturalness_score": {"type": "number", "minimum": 0, "maximum": 1},
                "partner_score": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": [
                "candidate_id",
                "context_score",
                "intent_score",
                "naturalness_score",
                "partner_score",
            ],
            "additionalProperties": False,
        }
        return {
            "type": "object",
            "properties": {"scores": {"type": "array", "items": item}},
            "required": ["scores"],
            "additionalProperties": False,
        }

    def generate_candidates(self, initials: str, count: int) -> GenerationCallResult:
        try:
            response = self.client.responses.create(
                model=self.generator_model_name,
                instructions=GENERATOR_INSTRUCTIONS,
                input=build_generator_input(initials, count),
                reasoning={"effort": settings.reasoning_effort},
                max_output_tokens=settings.max_output_tokens,
                text={
                    "verbosity": "low",
                    "format": {
                        "type": "json_schema",
                        "name": "bci_candidate_generation",
                        "strict": True,
                        "schema": self._generator_schema(),
                    },
                },
                store=False,
            )
            data = _parse_structured_json_response(response, "generator")
            candidates = [str(x).strip() for x in data.get("candidates", []) if str(x).strip()]
            return GenerationCallResult(candidates=candidates[:count], usage=self._usage(response))
        except Exception as exc:  # converted to app-safe errors; no secret leakage
            if isinstance(exc, LLMServiceError):
                raise
            self._raise_clean_error(exc)
            raise AssertionError("unreachable")

    def rank_candidates(self, candidates: list[GeneratedCandidate], context: str) -> RankingCallResult:
        candidate_pairs = [(c.candidate_id, c.text) for c in candidates]
        try:
            response = self.client.responses.create(
                model=self.ranker_model_name,
                instructions=RANKER_INSTRUCTIONS,
                input=build_ranker_input(candidate_pairs, context),
                reasoning={"effort": settings.reasoning_effort},
                max_output_tokens=settings.max_output_tokens,
                text={
                    "verbosity": "low",
                    "format": {
                        "type": "json_schema",
                        "name": "bci_candidate_ranking",
                        "strict": True,
                        "schema": self._ranker_schema(),
                    },
                },
                store=False,
            )
            data = _parse_structured_json_response(response, "ranker")
            valid_ids = {c.candidate_id for c in candidates}
            seen: set[str] = set()
            scores: list[CandidateScore] = []
            for item in data.get("scores", []):
                cid = str(item.get("candidate_id", ""))
                if cid not in valid_ids or cid in seen:
                    continue
                seen.add(cid)
                scores.append(
                    CandidateScore(
                        candidate_id=cid,
                        context_score=float(item["context_score"]),
                        intent_score=float(item["intent_score"]),
                        naturalness_score=float(item["naturalness_score"]),
                        partner_score=float(item["partner_score"]),
                    )
                )
            return RankingCallResult(scores=scores, usage=self._usage(response))
        except Exception as exc:
            if isinstance(exc, LLMServiceError):
                raise
            self._raise_clean_error(exc)
            raise AssertionError("unreachable")
