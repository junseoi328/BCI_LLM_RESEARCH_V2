from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import torch

from peft import PeftModel

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
)

from local_ft.common import (
    extract_initials,
    normalize_text,
    safe_json_candidates,
)


MODEL_DIR = Path(
    os.getenv(
        "LOCAL_MODEL_DIR",
        "local_models/bci_generator_lora_final",
    )
)


class LocalBCIGenerator:

    def __init__(
        self,
        model_dir: str | Path = MODEL_DIR,
        adapter_name: str = "best_adapter",
    ):

        self.model_dir = Path(
            model_dir
        )

        self.adapter_dir = (
            self.model_dir
            / adapter_name
        )

        metadata_path = (
            self.model_dir
            / "metadata.json"
        )

        if not metadata_path.exists():

            raise FileNotFoundError(
                f"metadata 없음: "
                f"{metadata_path}"
            )

        self.meta = json.loads(
            metadata_path.read_text(
                encoding="utf-8"
            )
        )

        if not (
            hasattr(torch, "xpu")
            and torch.xpu.is_available()
        ):

            raise RuntimeError(
                "Intel XPU 사용 불가"
            )

        self.device = "xpu"

        if (
            torch.xpu
            .is_bf16_supported()
        ):

            self.dtype = (
                torch.bfloat16
            )

        else:

            self.dtype = (
                torch.float32
            )

        # =============================================
        # TOKENIZER
        # =============================================

        self.tokenizer = (
            AutoTokenizer
            .from_pretrained(
                self.adapter_dir,
                trust_remote_code=True,
                use_fast=True,
            )
        )

        if (
            self.tokenizer
            .pad_token_id
            is None
        ):

            self.tokenizer.pad_token = (
                self.tokenizer.eos_token
            )

        # =============================================
        # BASE MODEL
        # =============================================

        base_model = (
            AutoModelForCausalLM
            .from_pretrained(
                self.meta[
                    "base_model"
                ],
                torch_dtype=
                    self.dtype,
                trust_remote_code=True,
                low_cpu_mem_usage=True,
            )
        )

        # =============================================
        # LoRA ADAPTER
        # =============================================

        self.model = (
            PeftModel
            .from_pretrained(
                base_model,
                self.adapter_dir,
            )
        )

        self.model.to(
            self.device
        )

        self.model.eval()

        self.lock = (
            threading.Lock()
        )

    # ==================================================
    # PROMPT
    # ==================================================

    def build_messages(
        self,
        initials: str,
        count: int,
    ) -> list[dict]:

        system_prompt = """
너는 한국어 BCI Speller의 후보 생성 모델이다.

사용자는 완전한 문장을 입력하지 못하고
한글 초성열만 입력한다.

너의 역할은 입력된 초성열과 정확히 일치하는
자연스럽고 실제 의사소통에 사용할 수 있는
한국어 단어 또는 문장을 여러 개 생성하는 것이다.

매우 중요:

1. 모든 후보의 한글 초성은 입력 초성열과
   정확히 일치해야 한다.

2. 초성을 추가하거나 삭제해서는 안 된다.

3. 일상 대화, 요청, 감정, 의료, 생활 표현 등
   실제 AAC/BCI 의사소통에서 사용할 수 있는
   표현을 우선한다.

4. 서로 의미가 지나치게 중복되는 후보만
   반복해서 생성하지 않는다.

5. 짧고 자연스러운 한국어 표현을 우선한다.

6. 출력은 반드시 JSON 형식으로 한다.

출력 형식:

{
  "candidates": [
    "후보1",
    "후보2",
    "후보3"
  ]
}

JSON 외에는 아무것도 출력하지 않는다.
""".strip()

        user_prompt = f"""
BCI 초성 입력:
{initials}

생성할 후보 수:
최대 {count}개

입력 초성과 정확히 일치하는
자연스러운 한국어 후보를 생성하세요.
""".strip()

        return [
            {
                "role":
                    "system",

                "content":
                    system_prompt,
            },

            {
                "role":
                    "user",

                "content":
                    user_prompt,
            },
        ]

    # ==================================================
    # RAW GENERATION
    # ==================================================

    @torch.no_grad()
    def generate_raw(
        self,
        initials: str,
        count: int = 16,
    ) -> str:

        messages = (
            self.build_messages(
                initials,
                count,
            )
        )

        prompt = (
            self.tokenizer
            .apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        )

        inputs = (
            self.tokenizer(
                prompt,
                return_tensors="pt",
            )
        )

        inputs = {
            key:
                value.to(
                    self.device
                )

            for key, value
            in inputs.items()
        }

        with self.lock:

            output = (
                self.model.generate(

                    **inputs,

                    max_new_tokens=320,

                    do_sample=True,

                    temperature=0.7,

                    top_p=0.9,

                    repetition_penalty=1.05,

                    pad_token_id=
                        self.tokenizer
                        .eos_token_id,
                )
            )

            torch.xpu.synchronize()

        generated = (
            output[0][
                inputs[
                    "input_ids"
                ].shape[1]:
            ]
        )

        raw = (
            self.tokenizer
            .decode(
                generated,
                skip_special_tokens=True,
            )
        )

        return raw

    # ==================================================
    # FILTER
    # ==================================================

    def _filter(
        self,
        initials: str,
        candidates: list[str],
        count: int,
    ) -> list[str]:

        result = []

        seen = set()

        for text in candidates:

            text = str(
                text
            ).strip()

            if not text:
                continue

            # -----------------------------------------
            # 가장 중요한 deterministic constraint
            # -----------------------------------------

            if (
                extract_initials(text)
                != initials
            ):
                continue

            key = (
                normalize_text(
                    text
                )
            )

            if (
                not key
                or key in seen
            ):
                continue

            seen.add(
                key
            )

            result.append(
                text
            )

            if (
                len(result)
                >= count
            ):
                break

        return result

    # ==================================================
    # PUBLIC GENERATION
    # ==================================================

    def generate(
        self,
        initials: str,
        count: int = 16,
    ) -> list[str]:

        raw = (
            self.generate_raw(
                initials,
                count,
            )
        )

        candidates = (
            safe_json_candidates(
                raw
            )
        )

        result = (
            self._filter(
                initials,
                candidates,
                count,
            )
        )

        return result

    # ==================================================
    # DEBUG
    # ==================================================

    def debug_generate(
        self,
        initials: str,
        count: int = 16,
    ) -> dict:

        raw = (
            self.generate_raw(
                initials,
                count,
            )
        )

        parsed = (
            safe_json_candidates(
                raw
            )
        )

        valid = (
            self._filter(
                initials,
                parsed,
                count,
            )
        )

        return {
            "initials":
                initials,

            "raw":
                raw,

            "parsed":
                parsed,

            "valid":
                valid,
        }