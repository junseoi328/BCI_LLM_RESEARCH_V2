from __future__ import annotations

import os

from app.korean.initials import extract_initials, normalize_text
from app.llm.openai_client import OpenAILanguageModelClient
from app.llm.phrase_memory_v2 import PhraseMemoryV2
from app.llm.types import (
    GenerationCallResult,
    RankingCallResult,
    TokenUsage,
)
from app.schemas import GeneratedCandidate


class LocalGeneratorCloudRankerClient:
    """
    Hybrid Fast BCI Language Client.

    Generator (한 번의 클라우드 왕복도 없이 즉시 실행):
        1) 사람이 검수한 phrase memory
           (research/phrase_memory/approved_bci_phrase_bank_v2.jsonl)
           -> 자주 쓰는 표현을 0ms, 100% 자연스러운 상태로 즉시 후보에 포함.
        2) 로컬 파인튜닝 Qwen2.5-0.5B + LoRA (local_ft.inference_final)
           -> phrase memory에 없는 표현까지 커버(long tail), XPU 있으면 XPU,
              없으면 CPU로 자동 폴백.

    Ranker:
        OpenAI 클라우드 모델 1회 호출로 문맥/상대/상황 기반 순위만 매긴다.
        (기존 파이프라인은 생성기도 클라우드였기 때문에 문맥 probe +
         diversity 생성 + 최종 랭킹까지 최대 4회의 순차 클라우드 호출이
         발생했다. 이 클라이언트는 생성 단계를 전부 로컬/즉시 처리로
         옮겨서, 응답마다 클라우드 호출을 사실상 랭킹 1회로 줄인다.)

    구조:
        BCI 초성 입력
        -> phrase memory 매칭 + 로컬 LoRA 생성 (병합, 중복 제거)
        -> deterministic 초성 exact-match 필터
        -> Luna 클라우드 컨텍스트 랭커 (1회)
        -> Top-K

    로컬 생성기가 어떤 이유로든 실패해도(드라이버 문제 등) 예외를 삼키고
    phrase memory만으로 계속 응답한다 - 절대 요청 전체를 실패시키지 않는다.

    Recovery (KeywordAE / FillMask):
        Top-K 초성열 매칭이 실패했을 때만 발동하는 별도 경로다. 이 시점에는
        "얼마나 빨리" 보다 "얼마나 정확히"가 훨씬 중요하므로 (SpeakFaster
        논문에서도 LLM 지연시간보다 사람의 검토 시간이 압도적으로 크다고
        보고한다), 로컬 생성기로는 시도조차 하지 않고 곧바로 문맥 인지가
        가능한 cloud_ranker에게 위임한다.
    """

    def __init__(self) -> None:
        from local_ft.inference_final import LocalBCIGenerator

        self.local_generator = LocalBCIGenerator()
        self.cloud_ranker = OpenAILanguageModelClient()

        self.memory = PhraseMemoryV2(
            os.getenv(
                "PHRASE_BANK_PATH",
                "research/phrase_memory/approved_bci_phrase_bank_v2.jsonl",
            )
        )
        self.memory_limit = int(os.getenv("PHRASE_MEMORY_LIMIT", "6"))

        # ========================================
        # BCILanguagePipeline이 반드시 요구하는
        # model interface attributes
        # ========================================

        base_name = self.local_generator.meta.get("base_model", "qwen2.5-0.5b")
        local_device = getattr(self.local_generator, "device", "cpu")

        self.generator_model_name = f"local-lora+memory:{base_name}({local_device})"
        self.ranker_model_name = self.cloud_ranker.ranker_model_name

    # ============================================
    # GENERATION (local, no network round trip)
    # ============================================

    def generate_candidates(self, initials: str, count: int) -> GenerationCallResult:
        if count <= 0:
            return GenerationCallResult(candidates=[], usage=TokenUsage(0, 0))

        memory_candidates = self.memory.candidates(initials, limit=self.memory_limit)

        # phrase memory(사람이 검수, 안전/자연스러움 보장)를 먼저 넣고
        # 로컬 모델 생성으로 다양성을 보충한다. (memory_augmented_client.py의
        # 검증된 병합 순서와 동일한 전략 - v7 평가에서 Acc@3가 상승했다.)
        merged: list[str] = []
        seen: set[str] = set()

        def candidate_stream():
            yield from memory_candidates
            # Only run inference if valid memory entries have not filled the request.
            try:
                yield from self.local_generator.generate(initials=initials, count=count)
            except Exception as exc:  # local model/driver hiccup must not break the request
                print(f"[HYBRID_GENERATOR] local generator error: {type(exc).__name__}: {exc}")

        for text in candidate_stream():
            text = str(text).strip()
            if not text:
                continue
            if extract_initials(text) != initials:
                continue
            key = normalize_text(text)
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(text)
            if len(merged) >= count:
                break

        return GenerationCallResult(
            candidates=merged,
            usage=TokenUsage(input_tokens=0, output_tokens=0),
        )

    # ============================================
    # RECOVERY (KeywordAE / FillMask, always cloud)
    # ============================================

    def generate_recovery_candidates(
        self,
        initials: str,
        count: int,
        *,
        spelled: dict[int, str] | None = None,
        reference_text: str | None = None,
        target_index: int | None = None,
        context: str = "",
    ) -> GenerationCallResult:
        return self.cloud_ranker.generate_recovery_candidates(
            initials,
            count,
            spelled=spelled,
            reference_text=reference_text,
            target_index=target_index,
            context=context,
        )

    # ============================================
    # CONTEXT RANKING (single cloud round trip)
    # ============================================

    def rank_candidates(
        self,
        candidates: list[GeneratedCandidate],
        context: str,
    ) -> RankingCallResult:
        return self.cloud_ranker.rank_candidates(candidates, context)
