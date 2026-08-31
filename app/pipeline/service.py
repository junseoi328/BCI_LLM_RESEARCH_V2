from __future__ import annotations

import os
import time
import uuid
from collections import Counter

from app.config import settings
from app.context.manager import build_context
from app.errors import LLMServiceError
from app.llm.diversity_generator import (
    generate_diversity_candidates,
)
from app.llm.factory import get_language_model_client
from app.llm.pricing import estimate_cost_usd
from app.llm.types import (
    LanguageModelClient,
    TokenUsage,
)
from app.logging.experiment_logger import log_prediction
from app.pipeline.diversity import remove_near_duplicates
from app.pipeline.eeg import normalized_eeg_hypotheses
from app.pipeline.fallback import local_candidates
from app.pipeline.filter import filter_candidates
from app.pipeline.hybrid import hybrid_action
from app.pipeline.normalize import normalize_request
from app.pipeline.rank import (
    local_rank_scores,
    merge_scores,
)
from app.schemas import (
    GeneratedCandidate,
    LatencyBreakdown,
    PredictionRequest,
    PredictionResponse,
    UsageSummary,
)


# ============================================================
# Utility
# ============================================================

def _usage_add(
    a: TokenUsage,
    b: TokenUsage,
) -> TokenUsage:
    return TokenUsage(
        a.input_tokens + b.input_tokens,
        a.output_tokens + b.output_tokens,
    )


def _env_int(
    name: str,
    default: int,
) -> int:
    try:
        return int(
            os.getenv(
                name,
                str(default),
            )
        )
    except ValueError:
        return default


def _env_float(
    name: str,
    default: float,
) -> float:
    try:
        return float(
            os.getenv(
                name,
                str(default),
            )
        )
    except ValueError:
        return default


def _ensemble_mode() -> str:
    """
    off
        base generator만 사용

    always
        base + diversity를 항상 같이 사용
        v5 정확도 실험용

    conditional
        base candidate 품질이 부족할 때만 diversity 사용
        추후 latency 최적화용
    """

    mode = (
        os.getenv(
            "ENSEMBLE_MODE",
            "off",
        )
        .strip()
        .lower()
    )

    if mode not in {
        "off",
        "always",
        "conditional",
    }:
        return "off"

    return mode


def _diversity_count() -> int:
    return max(
        0,
        _env_int(
            "DIVERSITY_GENERATION_COUNT",
            8,
        ),
    )


def _first_token_ratio(
    candidates: list[GeneratedCandidate],
) -> float:

    if not candidates:
        return 1.0

    first_tokens = []

    for candidate in candidates:
        text = candidate.text.strip()

        if not text:
            continue

        parts = text.split()

        if parts:
            first_tokens.append(
                parts[0]
            )

    if not first_tokens:
        return 1.0

    counts = Counter(
        first_tokens
    )

    max_count = max(
        counts.values()
    )

    return (
        max_count
        / len(first_tokens)
    )


def _should_run_diversity(
    valid_base: list[GeneratedCandidate],
) -> bool:

    mode = _ensemble_mode()

    if mode == "off":
        return False

    if mode == "always":
        return True

    # conditional mode
    min_valid = max(
        1,
        _env_int(
            "ENSEMBLE_MIN_VALID",
            6,
        ),
    )

    max_first_token_ratio = _env_float(
        "ENSEMBLE_MAX_FIRST_TOKEN_RATIO",
        0.50,
    )

    if len(
        valid_base
    ) < min_valid:
        return True

    if (
        _first_token_ratio(
            valid_base
        )
        >= max_first_token_ratio
    ):
        return True

    return False


def _supports_diversity_generator(
    model_client,
) -> bool:
    """
    실제 OpenAI client에는 .client가 있다.
    Mock client에는 없으므로 unit test에서는 자동으로 건너뛴다.
    """

    return (
        getattr(
            model_client,
            "client",
            None,
        )
        is not None
    )


# ============================================================
# Pipeline
# ============================================================

class BCILanguagePipeline:

    def __init__(
        self,
        model_client: LanguageModelClient | None = None,
    ):
        self.model_client = (
            model_client
            or get_language_model_client()
        )

    def predict(
        self,
        raw_request: PredictionRequest,
    ) -> PredictionResponse:

        total_start = time.perf_counter()

        request = normalize_request(
            raw_request
        )

        context = build_context(
            request
        )

        generation_ms = 0
        ranking_ms = 0

        usage = TokenUsage()

        warnings: list[str] = []

        fallback = "none"

        debug_generation: list[dict] = []

        pooled: list[
            GeneratedCandidate
        ] = []

        next_id = 1

        # ====================================================
        # EEG hypothesis별 generation
        # ====================================================

        for (
            initials,
            eeg_score,
        ) in normalized_eeg_hypotheses(
            request
        ):

            gen_start = time.perf_counter()

            base_success = False

            # ------------------------------------------------
            # 1. BASE GENERATOR
            # ------------------------------------------------

            try:
                gen_result = (
                    self.model_client
                    .generate_candidates(
                        initials,
                        settings.generation_count,
                    )
                )

                usage = _usage_add(
                    usage,
                    gen_result.usage,
                )

                base_raw = [
                    GeneratedCandidate(
                        candidate_id=(
                            f"c{next_id + i}"
                        ),
                        text=text,
                        source_initials=initials,
                        generation_order=i + 1,
                        eeg_score=eeg_score,
                    )
                    for (
                        i,
                        text,
                    ) in enumerate(
                        gen_result.candidates
                    )
                ]

                next_id += len(
                    base_raw
                )

                base_success = True

            except LLMServiceError as exc:

                if not settings.allow_local_fallback:
                    raise

                warnings.append(
                    f"generator:{exc.code}"
                )

                fallback = (
                    "local_phrase_bank"
                )

                base_raw = local_candidates(
                    initials,
                    eeg_score,
                    next_id,
                )

                next_id += len(
                    base_raw
                )

            base_valid = filter_candidates(
                base_raw,
                initials,
            )

            pooled.extend(
                base_valid
            )

            if settings.debug_mode:
                debug_generation.append(
                    {
                        "source": "base",
                        "initials": initials,
                        "eeg_score": eeg_score,
                        "raw_count": len(
                            base_raw
                        ),
                        "valid_count": len(
                            base_valid
                        ),
                        "raw": [
                            c.text
                            for c in base_raw
                        ],
                        "valid": [
                            c.text
                            for c in base_valid
                        ],
                    }
                )

            # ------------------------------------------------
            # 2. DIVERSITY GENERATOR
            # ------------------------------------------------

            diversity_used = False

            if (
                base_success
                and _supports_diversity_generator(
                    self.model_client
                )
                and _should_run_diversity(
                    base_valid
                )
                and _diversity_count() > 0
            ):

                diversity_used = True

                try:
                    diversity_result = (
                        generate_diversity_candidates(
                            model_client=self.model_client,
                            initials=initials,
                            count=_diversity_count(),
                            existing_candidates=[
                                c.text
                                for c in base_raw
                            ],
			     context=context,
                        )
                    )

                    usage = _usage_add(
                        usage,
                        diversity_result.usage,
                    )

                    diversity_raw = [
                        GeneratedCandidate(
                            candidate_id=(
                                f"c{next_id + i}"
                            ),
                            text=text,
                            source_initials=initials,
                            generation_order=(
                                len(base_raw)
                                + i
                                + 1
                            ),
                            eeg_score=eeg_score,
                        )
                        for (
                            i,
                            text,
                        ) in enumerate(
                            diversity_result.candidates
                        )
                    ]

                    next_id += len(
                        diversity_raw
                    )

                    diversity_valid = (
                        filter_candidates(
                            diversity_raw,
                            initials,
                        )
                    )

                    pooled.extend(
                        diversity_valid
                    )

                    if settings.debug_mode:
                        debug_generation.append(
                            {
                                "source": "diversity",
                                "initials": initials,
                                "eeg_score": eeg_score,
                                "raw_count": len(
                                    diversity_raw
                                ),
                                "valid_count": len(
                                    diversity_valid
                                ),
                                "raw": [
                                    c.text
                                    for c
                                    in diversity_raw
                                ],
                                "valid": [
                                    c.text
                                    for c
                                    in diversity_valid
                                ],
                            }
                        )

                except LLMServiceError as exc:
                    # Diversity는 보조 경로이므로
                    # 실패해도 base 결과는 살린다.
                    warnings.append(
                        "diversity_generator:"
                        + exc.code
                    )

            if (
                settings.debug_mode
                and not diversity_used
            ):
                debug_generation.append(
                    {
                        "source": "diversity",
                        "initials": initials,
                        "skipped": True,
                        "ensemble_mode": (
                            _ensemble_mode()
                        ),
                        "base_valid_count": (
                            len(base_valid)
                        ),
                        "first_token_ratio": (
                            _first_token_ratio(
                                base_valid
                            )
                        ),
                    }
                )

            generation_ms += int(
                (
                    time.perf_counter()
                    - gen_start
                )
                * 1000
            )

        # ====================================================
        # Cross-hypothesis duplicate handling
        # ====================================================

        best_by_text: dict[
            str,
            GeneratedCandidate,
        ] = {}

        for candidate in pooled:

            old = best_by_text.get(
                candidate.text
            )

            if old is None:
                best_by_text[
                    candidate.text
                ] = candidate

                continue

            old_eeg = (
                -1.0
                if old.eeg_score is None
                else old.eeg_score
            )

            new_eeg = (
                -1.0
                if candidate.eeg_score is None
                else candidate.eeg_score
            )

            if new_eeg > old_eeg:
                best_by_text[
                    candidate.text
                ] = candidate

        candidates = list(
            best_by_text.values()
        )

        candidates.sort(
            key=lambda candidate: (
                -(
                    candidate.eeg_score
                    or 0.0
                ),
                candidate.generation_order,
            )
        )

        candidates = remove_near_duplicates(
            candidates
        )

        # ====================================================
        # No candidate
        # ====================================================

        if not candidates:

            response = PredictionResponse(
                request_id=(
                    f"req_{uuid.uuid4().hex[:12]}"
                ),
                candidates=[],
                fallback="reinput",
                hybrid_action="need_more_input",
                latency=LatencyBreakdown(
                    generation_ms=(
                        generation_ms
                    ),
                    ranking_ms=0,
                    postprocess_ms=0,
                    total_ms=int(
                        (
                            time.perf_counter()
                            - total_start
                        )
                        * 1000
                    ),
                ),
                generator_model=(
                    self.model_client
                    .generator_model_name
                ),
                ranker_model=(
                    self.model_client
                    .ranker_model_name
                ),
                usage=UsageSummary(
                    input_tokens=(
                        usage.input_tokens
                    ),
                    output_tokens=(
                        usage.output_tokens
                    ),
                    total_tokens=(
                        usage.total_tokens
                    ),
                ),
                pipeline_version=(
                    settings.pipeline_version
                ),
                generator_prompt_version=(
                    settings
                    .generator_prompt_version
                ),
                ranker_prompt_version=(
                    settings
                    .ranker_prompt_version
                ),
                warnings=(
                    warnings
                    + [
                        "no_valid_candidate"
                    ]
                ),
                debug=(
                    {
                        "ensemble_mode": (
                            _ensemble_mode()
                        ),
                        "generation": (
                            debug_generation
                        ),
                    }
                    if settings.debug_mode
                    else None
                ),
            )

            log_prediction(
                request,
                response,
            )

            return response

        # ====================================================
        # Ranking
        # ====================================================

        rank_start = time.perf_counter()

        if settings.use_llm_ranker:

            try:
                rank_result = (
                    self.model_client
                    .rank_candidates(
                        candidates,
                        context,
                    )
                )

                usage = _usage_add(
                    usage,
                    rank_result.usage,
                )

                rank_rows = (
                    rank_result.scores
                )

            except LLMServiceError as exc:

                warnings.append(
                    f"ranker:{exc.code}"
                )

                fallback = (
                    "local_ranker"
                    if fallback == "none"
                    else (
                        fallback
                        + "+local_ranker"
                    )
                )

                rank_rows = (
                    local_rank_scores(
                        candidates
                    )
                )

        else:
            rank_rows = (
                local_rank_scores(
                    candidates
                )
            )

            warnings.append(
                "llm_ranker_disabled"
            )

        ranking_ms = int(
            (
                time.perf_counter()
                - rank_start
            )
            * 1000
        )

        # ====================================================
        # Score fusion
        # ====================================================

        ranked = merge_scores(
            candidates,
            rank_rows,
        )

        top = [
            candidate.model_copy(
                update={
                    "rank": i + 1,
                }
            )
            for (
                i,
                candidate,
            ) in enumerate(
                ranked[
                    : request.top_k
                ]
            )
        ]

        if (
            len(top)
            < request.top_k
            and fallback == "none"
        ):
            fallback = "reinput"

        # ====================================================
        # Hybrid action
        # ====================================================

        post_start = time.perf_counter()

        action = hybrid_action(
            request.experiment_mode,
            top,
        )

        post_ms = int(
            (
                time.perf_counter()
                - post_start
            )
            * 1000
        )

        total_ms = int(
            (
                time.perf_counter()
                - total_start
            )
            * 1000
        )

        # ====================================================
        # Cost
        # ====================================================

        estimated = None

        if (
            self.model_client
            .generator_model_name
            ==
            self.model_client
            .ranker_model_name
        ):

            estimated = estimate_cost_usd(
                self.model_client
                .generator_model_name,
                usage.input_tokens,
                usage.output_tokens,
            )

        # ====================================================
        # Response
        # ====================================================

        response = PredictionResponse(
            request_id=(
                f"req_{uuid.uuid4().hex[:12]}"
            ),
            candidates=top,
            fallback=fallback,
            hybrid_action=action,
            latency=LatencyBreakdown(
                generation_ms=(
                    generation_ms
                ),
                ranking_ms=(
                    ranking_ms
                ),
                postprocess_ms=(
                    post_ms
                ),
                total_ms=(
                    total_ms
                ),
            ),
            generator_model=(
                self.model_client
                .generator_model_name
            ),
            ranker_model=(
                self.model_client
                .ranker_model_name
            ),
            usage=UsageSummary(
                input_tokens=(
                    usage.input_tokens
                ),
                output_tokens=(
                    usage.output_tokens
                ),
                total_tokens=(
                    usage.total_tokens
                ),
                estimated_cost_usd=(
                    estimated
                ),
            ),
            pipeline_version=(
                settings.pipeline_version
            ),
            generator_prompt_version=(
                settings
                .generator_prompt_version
            ),
            ranker_prompt_version=(
                settings
                .ranker_prompt_version
            ),
            warnings=warnings,
            debug=(
                {
                    "context": context,
                    "ensemble_mode": (
                        _ensemble_mode()
                    ),
                    "diversity_count": (
                        _diversity_count()
                    ),
                    "generation": (
                        debug_generation
                    ),
                    "pooled_count": (
                        len(pooled)
                    ),
                    "diverse_count": (
                        len(candidates)
                    ),
                }
                if settings.debug_mode
                else None
            ),
        )

        log_prediction(
            request,
            response,
        )

        return response