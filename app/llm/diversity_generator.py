from __future__ import annotations

import json

from app.config import settings
from app.errors import LLMServiceError
from app.llm.diversity_prompt import (
    DIVERSITY_GENERATOR_INSTRUCTIONS,
    build_diversity_input,
)
from app.llm.types import (
    GenerationCallResult,
    TokenUsage,
)


def _usage_add(
    a: TokenUsage,
    b: TokenUsage,
) -> TokenUsage:
    return TokenUsage(
        a.input_tokens + b.input_tokens,
        a.output_tokens + b.output_tokens,
    )


def _response_usage(
    model_client,
    response,
) -> TokenUsage:

    usage_fn = getattr(
        model_client,
        "_usage",
        None,
    )

    if callable(usage_fn):
        return usage_fn(response)

    usage = getattr(
        response,
        "usage",
        None,
    )

    if usage is None:
        return TokenUsage()

    return TokenUsage(
        input_tokens=int(
            getattr(
                usage,
                "input_tokens",
                0,
            )
            or 0
        ),
        output_tokens=int(
            getattr(
                usage,
                "output_tokens",
                0,
            )
            or 0
        ),
    )


def _generator_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "items": {
                    "type": "string",
                },
            }
        },
        "required": [
            "candidates",
        ],
        "additionalProperties": False,
    }


def _parse_json(text: str) -> dict:
    """
    Structured Output이 정상이라면 바로 json.loads 된다.

    혹시 앞뒤에 불필요한 문자열이 붙은 경우에는
    가장 바깥 JSON object를 한 번 더 복구 시도한다.
    """

    text = (
        text
        or ""
    ).strip()

    if not text:
        raise LLMServiceError(
            "structured_output_error",
            "Diversity generator가 빈 응답을 반환했습니다.",
            retryable=True,
        )

    try:
        data = json.loads(text)

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "JSON root is not an object"
            )

        return data

    except (
        json.JSONDecodeError,
        ValueError,
    ):
        pass

    start = text.find("{")
    end = text.rfind("}")

    if (
        start >= 0
        and end > start
    ):
        try:
            data = json.loads(
                text[start:end + 1]
            )

            if isinstance(
                data,
                dict,
            ):
                return data

        except json.JSONDecodeError:
            pass

    raise LLMServiceError(
        "structured_output_error",
        "Diversity generator의 JSON 응답을 해석하지 못했습니다.",
        retryable=True,
    )


def generate_diversity_candidates(
    model_client,
    initials: str,
    count: int,
    existing_candidates: list[str],
    context: str,
) -> GenerationCallResult:

    """
    OpenAILanguageModelClient의 기존 base generator를 건드리지 않고
    보조 diversity generation을 한 번 수행한다.

    malformed structured output일 때만 최대 1회 추가 시도한다.
    """

    if count <= 0:
        return GenerationCallResult(
            candidates=[],
            usage=TokenUsage(),
        )

    client = getattr(
        model_client,
        "client",
        None,
    )

    model_name = getattr(
        model_client,
        "generator_model_name",
        None,
    )

    # MockLanguageModelClient 등에서는 ensemble을 건너뛴다.
    if (
        client is None
        or model_name is None
    ):
        return GenerationCallResult(
            candidates=[],
            usage=TokenUsage(),
        )

    total_usage = TokenUsage()

    last_parse_error: LLMServiceError | None = None

    # Structured output parse failure인 경우만 한 번 더 시도.
    for attempt in range(2):

        try:
            response = client.responses.create(
                model=model_name,
                instructions=DIVERSITY_GENERATOR_INSTRUCTIONS,
                input=build_diversity_input(
                    initials=initials,
                    count=count,
    		    existing_candidates=existing_candidates,
       		    context=context,
                ),
                reasoning={
                    "effort": settings.reasoning_effort,
                },
                max_output_tokens=settings.max_output_tokens,
                text={
                    "verbosity": "low",
                    "format": {
                        "type": "json_schema",
                        "name": "bci_diversity_candidate_generation",
                        "strict": True,
                        "schema": _generator_schema(),
                    },
                },
                store=False,
            )

            total_usage = _usage_add(
                total_usage,
                _response_usage(
                    model_client,
                    response,
                ),
            )

            try:
                data = _parse_json(
                    response.output_text
                )

            except LLMServiceError as exc:
                last_parse_error = exc

                if attempt == 0:
                    continue

                raise

            raw = data.get(
                "candidates",
                [],
            )

            candidates = []

            seen = set()

            for item in raw:
                text = str(
                    item
                ).strip()

                if not text:
                    continue

                if text in seen:
                    continue

                seen.add(text)

                candidates.append(text)

                if len(
                    candidates
                ) >= count:
                    break

            return GenerationCallResult(
                candidates=candidates,
                usage=total_usage,
            )

        except LLMServiceError:
            raise

        except Exception as exc:

            cleaner = getattr(
                model_client,
                "_raise_clean_error",
                None,
            )

            if callable(cleaner):
                cleaner(exc)

            raise LLMServiceError(
                "diversity_generator_error",
                "Diversity generator 호출에 실패했습니다.",
                retryable=True,
            ) from exc

    if last_parse_error is not None:
        raise last_parse_error

    return GenerationCallResult(
        candidates=[],
        usage=total_usage,
    )