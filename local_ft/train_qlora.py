from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

import torch

from datasets import load_dataset

from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
)

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
)


TRAIN_FILE = (
    "training_v2/data/openai/"
    "train_sft_v2.jsonl"
)

DEV_FILE = (
    "training_v2/data/openai/"
    "dev_sft_v2.jsonl"
)

OUTPUT_DIR = Path(
    "local_models/"
    "bci_generator_lora_v1"
)

BASE_MODEL = os.getenv(
    "LOCAL_BASE_MODEL",
    "Qwen/Qwen2.5-3B-Instruct",
)

MAX_LENGTH = int(
    os.getenv(
        "LOCAL_MAX_LENGTH",
        "1024",
    )
)


class CompletionCollator:

    def __init__(
        self,
        tokenizer,
    ):
        self.tokenizer = tokenizer

    def __call__(
        self,
        features,
    ):

        max_len = max(
            len(x["input_ids"])
            for x in features
        )

        input_ids = []
        attention_mask = []
        labels = []

        pad_id = (
            self.tokenizer.pad_token_id
        )

        for feature in features:

            ids = feature[
                "input_ids"
            ]

            mask = feature[
                "attention_mask"
            ]

            lbs = feature[
                "labels"
            ]

            pad = (
                max_len
                - len(ids)
            )

            input_ids.append(
                ids
                + [pad_id] * pad
            )

            attention_mask.append(
                mask
                + [0] * pad
            )

            labels.append(
                lbs
                + [-100] * pad
            )

        return {
            "input_ids":
                torch.tensor(
                    input_ids,
                    dtype=torch.long,
                ),

            "attention_mask":
                torch.tensor(
                    attention_mask,
                    dtype=torch.long,
                ),

            "labels":
                torch.tensor(
                    labels,
                    dtype=torch.long,
                ),
        }


def main():

    if not torch.cuda.is_available():

        raise RuntimeError(
            "CUDA GPU가 필요합니다."
        )

    print("=" * 70)
    print("BCI GENERATOR QLoRA TRAINING")
    print("=" * 70)

    print("Base model:", BASE_MODEL)
    print("Train:", TRAIN_FILE)
    print("Dev:", DEV_FILE)

    # --------------------------------------------------
    # TOKENIZER
    # --------------------------------------------------

    tokenizer = (
        AutoTokenizer
        .from_pretrained(
            BASE_MODEL,
            use_fast=True,
            trust_remote_code=True,
        )
    )

    if tokenizer.pad_token is None:

        tokenizer.pad_token = (
            tokenizer.eos_token
        )

    tokenizer.padding_side = "right"

    # --------------------------------------------------
    # 4-bit QLoRA
    # --------------------------------------------------

    if torch.cuda.is_bf16_supported():

        compute_dtype = (
            torch.bfloat16
        )

    else:

        compute_dtype = (
            torch.float16
        )

    quant_config = (
        BitsAndBytesConfig(

            load_in_4bit=True,

            bnb_4bit_quant_type=
                "nf4",

            bnb_4bit_use_double_quant=
                True,

            bnb_4bit_compute_dtype=
                compute_dtype,
        )
    )

    model = (
        AutoModelForCausalLM
        .from_pretrained(

            BASE_MODEL,

            quantization_config=
                quant_config,

            device_map="auto",

            trust_remote_code=True,
        )
    )

    model.config.use_cache = False

    model = (
        prepare_model_for_kbit_training(
            model,
            use_gradient_checkpointing=True,
        )
    )

    # --------------------------------------------------
    # LoRA
    # --------------------------------------------------

    lora_config = LoraConfig(

        r=16,

        lora_alpha=32,

        lora_dropout=0.05,

        bias="none",

        task_type="CAUSAL_LM",

        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",

            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )

    model = get_peft_model(
        model,
        lora_config,
    )

    model.print_trainable_parameters()

    # --------------------------------------------------
    # DATASET
    # --------------------------------------------------

    dataset = load_dataset(
        "json",
        data_files={
            "train":
                TRAIN_FILE,

            "validation":
                DEV_FILE,
        },
    )

    def encode(example):

        messages = (
            example["messages"]
        )

        if len(messages) < 3:

            raise ValueError(
                "messages가 3개 미만"
            )

        # assistant 이전까지만 prompt
        prompt_messages = (
            messages[:-1]
        )

        assistant_content = (
            messages[-1][
                "content"
            ]
        )

        prompt_text = (
            tokenizer
            .apply_chat_template(

                prompt_messages,

                tokenize=False,

                add_generation_prompt=True,
            )
        )

        full_text = (
            prompt_text
            + assistant_content
            + tokenizer.eos_token
        )

        prompt_ids = (
            tokenizer(

                prompt_text,

                add_special_tokens=False,

            )["input_ids"]
        )

        full = tokenizer(

            full_text,

            add_special_tokens=False,

            truncation=True,

            max_length=
                MAX_LENGTH,
        )

        input_ids = (
            full["input_ids"]
        )

        attention_mask = (
            full[
                "attention_mask"
            ]
        )

        labels = (
            input_ids.copy()
        )

        # system/user prompt는 loss 제외
        prompt_length = min(
            len(prompt_ids),
            len(labels),
        )

        labels[
            :prompt_length
        ] = [
            -100
        ] * prompt_length

        return {
            "input_ids":
                input_ids,

            "attention_mask":
                attention_mask,

            "labels":
                labels,
        }

    encoded = dataset.map(
        encode,
        remove_columns=
            dataset[
                "train"
            ].column_names,
    )

    # --------------------------------------------------
    # TRAINING ARGUMENTS
    # transformers 버전 차이 대응
    # --------------------------------------------------

    kwargs = {

        "output_dir":
            str(OUTPUT_DIR),

        "num_train_epochs":
            3,

        "per_device_train_batch_size":
            1,

        "per_device_eval_batch_size":
            1,

        "gradient_accumulation_steps":
            8,

        "learning_rate":
            2e-4,

        "warmup_ratio":
            0.05,

        "weight_decay":
            0.01,

        "logging_steps":
            5,

        "eval_steps":
            25,

        "save_steps":
            25,

        "save_total_limit":
            2,

        "load_best_model_at_end":
            True,

        "metric_for_best_model":
            "eval_loss",

        "greater_is_better":
            False,

        "gradient_checkpointing":
            True,

        "optim":
            "paged_adamw_8bit",

        "bf16":
            torch.cuda
            .is_bf16_supported(),

        "fp16":
            not torch.cuda
            .is_bf16_supported(),

        "report_to":
            [],

        "remove_unused_columns":
            False,

        "seed":
            20260902,
    }

    signature = (
        inspect.signature(
            TrainingArguments.__init__
        )
    )

    if (
        "eval_strategy"
        in signature.parameters
    ):

        kwargs[
            "eval_strategy"
        ] = "steps"

    else:

        kwargs[
            "evaluation_strategy"
        ] = "steps"

    kwargs[
        "save_strategy"
    ] = "steps"

    training_args = (
        TrainingArguments(
            **kwargs
        )
    )

    trainer = Trainer(

        model=model,

        args=
            training_args,

        train_dataset=
            encoded["train"],

        eval_dataset=
            encoded[
                "validation"
            ],

        data_collator=
            CompletionCollator(
                tokenizer
            ),
    )

    print()
    print("=" * 70)
    print("START TRAINING")
    print("=" * 70)

    trainer.train()

    # --------------------------------------------------
    # SAVE
    # --------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    trainer.model.save_pretrained(
        OUTPUT_DIR
    )

    tokenizer.save_pretrained(
        OUTPUT_DIR
    )

    metadata = {

        "base_model":
            BASE_MODEL,

        "adapter_path":
            str(OUTPUT_DIR),

        "train_file":
            TRAIN_FILE,

        "dev_file":
            DEV_FILE,

        "epochs":
            3,

        "lora_r":
            16,

        "lora_alpha":
            32,

        "max_length":
            MAX_LENGTH,
    }

    (
        OUTPUT_DIR
        / "bci_training_metadata.json"
    ).write_text(

        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        ),

        encoding="utf-8",
    )

    print()
    print("=" * 70)
    print("TRAINING COMPLETE")
    print("=" * 70)

    print(
        "Adapter:",
        OUTPUT_DIR
    )


if __name__ == "__main__":
    main()