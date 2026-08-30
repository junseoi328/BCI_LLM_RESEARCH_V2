from __future__ import annotations

import time
import uuid

from app.config import settings
from app.context.manager import build_context
from app.errors import LLMServiceError
from app.llm.factory import get_language_model_client
from app.llm.pricing import estimate_cost_usd
from app.llm.types import LanguageModelClient, TokenUsage
from app.logging.experiment_logger import log_prediction
from app.pipeline.diversity import remove_near_duplicates
from app.pipeline.eeg import normalized_eeg_hypotheses
from app.pipeline.fallback import local_candidates
from app.pipeline.filter import filter_candidates
from app.pipeline.hybrid import hybrid_action
from app.pipeline.normalize import normalize_request
from app.pipeline.rank import local_rank_scores, merge_scores
from app.schemas import (
    GeneratedCandidate,
    LatencyBreakdown,
    PredictionRequest,
    PredictionResponse,
    UsageSummary,
)


def _usage_add(a: TokenUsage, b: TokenUsage) -> TokenUsage:
    return TokenUsage(a.input_tokens + b.input_tokens, a.output_tokens + b.output_tokens)


class BCILanguagePipeline:
    def __init__(self, model_client: LanguageModelClient | None = None):
        self.model_client = model_client or get_language_model_client()

    def predict(self, raw_request: PredictionRequest) -> PredictionResponse:
        total_start = time.perf_counter()
        request = normalize_request(raw_request)
        context = build_context(request)

        generation_ms = 0
        ranking_ms = 0
        usage = TokenUsage()
        warnings: list[str] = []
        fallback = "none"
        debug_generation: list[dict] = []

        pooled: list[GeneratedCandidate] = []
        next_id = 1

        for initials, eeg_score in normalized_eeg_hypotheses(request):
            gen_start = time.perf_counter()
            try:
                gen_result = self.model_client.generate_candidates(initials, settings.generation_count)
                usage = _usage_add(usage, gen_result.usage)
                raw_candidates = [
                    GeneratedCandidate(
                        candidate_id=f"c{next_id+i}",
                        text=text,
                        source_initials=initials,
                        generation_order=i + 1,
                        eeg_score=eeg_score,
                    )
                    for i, text in enumerate(gen_result.candidates)
                ]
                next_id += len(raw_candidates)
            except LLMServiceError as exc:
                if not settings.allow_local_fallback:
                    raise
                warnings.append(f"generator:{exc.code}")
                fallback = "local_phrase_bank"
                raw_candidates = local_candidates(initials, eeg_score, next_id)
                next_id += len(raw_candidates)
            generation_ms += int((time.perf_counter() - gen_start) * 1000)

            valid = filter_candidates(raw_candidates, initials)
            if settings.debug_mode:
                debug_generation.append(
                    {
                        "initials": initials,
                        "eeg_score": eeg_score,
                        "raw": [c.text for c in raw_candidates],
                        "valid": [c.text for c in valid],
                    }
                )
            pooled.extend(valid)

        # Cross-hypothesis duplicate handling: keep the version with stronger EEG evidence.
        best_by_text: dict[str, GeneratedCandidate] = {}
        for c in pooled:
            old = best_by_text.get(c.text)
            if old is None:
                best_by_text[c.text] = c
            else:
                old_eeg = -1.0 if old.eeg_score is None else old.eeg_score
                new_eeg = -1.0 if c.eeg_score is None else c.eeg_score
                if new_eeg > old_eeg:
                    best_by_text[c.text] = c

        candidates = list(best_by_text.values())
        candidates.sort(key=lambda c: (-(c.eeg_score or 0.0), c.generation_order))
        candidates = remove_near_duplicates(candidates)

        if not candidates:
            response = PredictionResponse(
                request_id=f"req_{uuid.uuid4().hex[:12]}",
                candidates=[],
                fallback="reinput",
                hybrid_action="need_more_input",
                latency=LatencyBreakdown(
                    generation_ms=generation_ms,
                    ranking_ms=0,
                    postprocess_ms=0,
                    total_ms=int((time.perf_counter() - total_start) * 1000),
                ),
                generator_model=self.model_client.generator_model_name,
                ranker_model=self.model_client.ranker_model_name,
                usage=UsageSummary(
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    total_tokens=usage.total_tokens,
                ),
                pipeline_version=settings.pipeline_version,
                generator_prompt_version=settings.generator_prompt_version,
                ranker_prompt_version=settings.ranker_prompt_version,
                warnings=warnings + ["no_valid_candidate"],
                debug={"generation": debug_generation} if settings.debug_mode else None,
            )
            log_prediction(request, response)
            return response

        rank_start = time.perf_counter()
        if settings.use_llm_ranker:
            try:
                rank_result = self.model_client.rank_candidates(candidates, context)
                usage = _usage_add(usage, rank_result.usage)
                rank_rows = rank_result.scores
            except LLMServiceError as exc:
                warnings.append(f"ranker:{exc.code}")
                fallback = "local_ranker" if fallback == "none" else fallback + "+local_ranker"
                rank_rows = local_rank_scores(candidates)
        else:
            rank_rows = local_rank_scores(candidates)
            warnings.append("llm_ranker_disabled")
        ranking_ms = int((time.perf_counter() - rank_start) * 1000)

        ranked = merge_scores(candidates, rank_rows)
        top = [c.model_copy(update={"rank": i + 1}) for i, c in enumerate(ranked[: request.top_k])]
        if len(top) < request.top_k and fallback == "none":
            fallback = "reinput"

        post_start = time.perf_counter()
        action = hybrid_action(request.experiment_mode, top)
        post_ms = int((time.perf_counter() - post_start) * 1000)
        total_ms = int((time.perf_counter() - total_start) * 1000)

        # Approximate cost: generation and ranking may use different models, so calculate separately
        # only when both use the same model. Model-benchmark scripts can record finer-grained costs.
        estimated = None
        if self.model_client.generator_model_name == self.model_client.ranker_model_name:
            estimated = estimate_cost_usd(
                self.model_client.generator_model_name,
                usage.input_tokens,
                usage.output_tokens,
            )

        response = PredictionResponse(
            request_id=f"req_{uuid.uuid4().hex[:12]}",
            candidates=top,
            fallback=fallback,
            hybrid_action=action,
            latency=LatencyBreakdown(
                generation_ms=generation_ms,
                ranking_ms=ranking_ms,
                postprocess_ms=post_ms,
                total_ms=total_ms,
            ),
            generator_model=self.model_client.generator_model_name,
            ranker_model=self.model_client.ranker_model_name,
            usage=UsageSummary(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens,
                estimated_cost_usd=estimated,
            ),
            pipeline_version=settings.pipeline_version,
            generator_prompt_version=settings.generator_prompt_version,
            ranker_prompt_version=settings.ranker_prompt_version,
            warnings=warnings,
            debug={
                "context": context,
                "generation": debug_generation,
                "pooled_count": len(pooled),
                "diverse_count": len(candidates),
            }
            if settings.debug_mode
            else None,
        )
        log_prediction(request, response)
        return response
