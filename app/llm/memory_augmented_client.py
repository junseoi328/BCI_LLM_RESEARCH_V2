from __future__ import annotations

import os

from app.llm.openai_client import (
    OpenAILanguageModelClient,
)

from app.llm.phrase_memory_v2 import (
    PhraseMemoryV2,
)

from app.llm.types import (
    GenerationCallResult,
)

from training_v2.common import (
    extract_initials,
    normalize_text,
)


class MemoryAugmentedLanguageModelClient(
    OpenAILanguageModelClient
):

    def __init__(
        self,
        *args,
        phrase_bank_path: str | None = None,
        memory_limit: int | None = None,
        **kwargs,
    ):

        super().__init__(
            *args,
            **kwargs,
        )

        self.memory_limit = (
            memory_limit
            if memory_limit is not None
            else int(
                os.getenv(
                    "PHRASE_MEMORY_LIMIT",
                    "6",
                )
            )
        )

        self.memory = PhraseMemoryV2(
            phrase_bank_path
            or os.getenv(
                "PHRASE_BANK_PATH",
                (
                    "research/phrase_memory/"
                    "approved_bci_phrase_bank_v2.jsonl"
                ),
            )
        )

    def generate_candidates(
        self,
        initials: str,
        count: int,
    ) -> GenerationCallResult:

        # --------------------------------
        # 1. 기존 Luna 후보
        # --------------------------------

        base_result = (
            super()
            .generate_candidates(
                initials,
                count,
            )
        )

        base_candidates = [
            str(x).strip()
            for x
            in base_result.candidates
            if str(x).strip()
        ]

        # --------------------------------
        # 2. Phrase Memory 후보
        # --------------------------------

        memory_candidates = (
            self.memory.candidates(
                initials,
                limit=self.memory_limit,
            )
        )

        # --------------------------------
        # 3. Memory를 먼저 넣고
        #    Luna 후보로 diversity 보충
        # --------------------------------

        merged = []

        seen = set()

        sources = (
            memory_candidates
            + base_candidates
        )

        for text in sources:

            text = str(
                text
            ).strip()

            if not text:
                continue

            # 여기도 hard constraint
            if (
                extract_initials(text)
                != initials
            ):
                continue

            key = normalize_text(
                text
            )

            if key in seen:
                continue

            seen.add(key)

            merged.append(
                text
            )

            # downstream 크기를
            # 기존 generator count와 동일하게 유지
            if len(merged) >= count:
                break

        return GenerationCallResult(
            candidates=merged,
            usage=base_result.usage,
        )