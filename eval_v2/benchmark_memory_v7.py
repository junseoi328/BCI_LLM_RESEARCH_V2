from __future__ import annotations

import json
import statistics
from pathlib import Path

from app.llm.memory_augmented_client import (
    MemoryAugmentedLanguageModelClient,
)

from app.llm.openai_client import (
    OpenAILanguageModelClient,
)

from app.pipeline.service import (
    BCILanguagePipeline,
)

from app.schemas import (
    PredictionRequest,
)

from training_v2.common import (
    normalize_text,
    read_jsonl,
)


DATASET = Path(
    "training_v2/data/"
    "hard50_v2.jsonl"
)

REPORT = Path(
    "eval_v2/reports/"
    "memory_v7_comparison.json"
)


def find_rank(
    target: str,
    predictions: list[str],
):

    target_norm = normalize_text(
        target
    )

    for index, prediction in enumerate(
        predictions,
        start=1,
    ):

        if (
            normalize_text(prediction)
            == target_norm
        ):

            return index

    return None


def evaluate(
    label: str,
    pipeline: BCILanguagePipeline,
    rows: list[dict],
):

    results = []

    for i, row in enumerate(
        rows,
        start=1,
    ):

        try:

            response = (
                pipeline.predict(
                    PredictionRequest(
                        bci_input=
                            row[
                                "bci_input"
                            ],

                        partner=
                            row.get(
                                "partner",
                                "other",
                            ),

                        situation=
                            row.get(
                                "situation",
                                "general",
                            ),

                        current_sentence=
                            row.get(
                                "current_sentence",
                                "",
                            ),

                        recent_context=
                            row.get(
                                "recent_context",
                                [],
                            ),

                        top_k=3,
                    )
                )
            )

            predictions = [
                candidate.text
                for candidate
                in response.candidates
            ]

            rank = find_rank(
                row["target"],
                predictions,
            )

            latency = (
                response
                .latency
                .total_ms
            )

            result = {

                "id":
                    row["id"],

                "target":
                    row["target"],

                "bci_input":
                    row[
                        "bci_input"
                    ],

                "predictions":
                    predictions,

                "rank":
                    rank,

                "latency_ms":
                    latency,

                "fallback":
                    response.fallback,

                "error":
                    None,
            }

            results.append(
                result
            )

            print(
                f"[{label} "
                f"{i:03d}/"
                f"{len(rows):03d}] "
                f"rank={rank} "
                f"target="
                f"{row['target']} "
                f"preds="
                f"{predictions}"
            )

        except Exception as exc:

            result = {

                "id":
                    row["id"],

                "target":
                    row["target"],

                "bci_input":
                    row[
                        "bci_input"
                    ],

                "predictions":
                    [],

                "rank":
                    None,

                "latency_ms":
                    None,

                "fallback":
                    "",

                "error":
                    (
                        f"{type(exc).__name__}:"
                        f"{exc}"
                    ),
            }

            results.append(
                result
            )

            print(
                f"[{label} "
                f"{i:03d}/"
                f"{len(rows):03d}] "
                f"ERROR="
                f"{type(exc).__name__}:"
                f"{exc}"
            )

    n = len(
        results
    )

    latencies = [
        row["latency_ms"]
        for row
        in results
        if (
            row["latency_ms"]
            is not None
        )
    ]

    acc1 = (
        sum(
            row["rank"] == 1
            for row
            in results
        )
        / n
    )

    acc3 = (
        sum(
            isinstance(
                row["rank"],
                int,
            )
            and row["rank"] <= 3

            for row
            in results
        )
        / n
    )

    mrr = (
        sum(
            (
                1.0 / row["rank"]
                if isinstance(
                    row["rank"],
                    int,
                )
                else 0.0
            )

            for row
            in results
        )
        / n
    )

    error_rate = (
        sum(
            row["error"]
            is not None

            for row
            in results
        )
        / n
    )

    summary = {

        "label":
            label,

        "n":
            n,

        "acc_at_1":
            acc1,

        "acc_at_3":
            acc3,

        "mrr":
            mrr,

        "mean_latency_ms":
            (
                statistics.mean(
                    latencies
                )
                if latencies
                else None
            ),

        "service_error_rate":
            error_rate,
    }

    return (
        results,
        summary,
    )


def main():

    if not DATASET.exists():

        raise RuntimeError(
            f"Dataset 없음: {DATASET}"
        )

    rows = read_jsonl(
        DATASET
    )

    print()
    print(
        "=" * 70
    )

    print(
        "A: V6.3 LUNA ONLY"
    )

    print(
        "=" * 70
    )

    base_pipeline = (
        BCILanguagePipeline(
            OpenAILanguageModelClient()
        )
    )

    (
        base_results,
        base_summary,
    ) = evaluate(
        "v6_3",
        base_pipeline,
        rows,
    )

    print()
    print(
        "=" * 70
    )

    print(
        "B: V7 MEMORY"
    )

    print(
        "=" * 70
    )

    memory_pipeline = (
        BCILanguagePipeline(
            MemoryAugmentedLanguageModelClient()
        )
    )

    (
        memory_results,
        memory_summary,
    ) = evaluate(
        "v7_memory",
        memory_pipeline,
        rows,
    )

    comparison = {

        "base":
            base_summary,

        "v7_memory":
            memory_summary,

        "delta": {

            "acc_at_1":
                (
                    memory_summary[
                        "acc_at_1"
                    ]
                    -
                    base_summary[
                        "acc_at_1"
                    ]
                ),

            "acc_at_3":
                (
                    memory_summary[
                        "acc_at_3"
                    ]
                    -
                    base_summary[
                        "acc_at_3"
                    ]
                ),

            "mrr":
                (
                    memory_summary[
                        "mrr"
                    ]
                    -
                    base_summary[
                        "mrr"
                    ]
                ),

            "mean_latency_ms":
                (
                    None
                    if (
                        base_summary[
                            "mean_latency_ms"
                        ]
                        is None
                        or
                        memory_summary[
                            "mean_latency_ms"
                        ]
                        is None
                    )
                    else
                    (
                        memory_summary[
                            "mean_latency_ms"
                        ]
                        -
                        base_summary[
                            "mean_latency_ms"
                        ]
                    )
                ),
        },

        "case_changes": [],
    }

    for base, memory in zip(
        base_results,
        memory_results,
    ):

        base_success = (
            isinstance(
                base["rank"],
                int,
            )
            and base["rank"] <= 3
        )

        memory_success = (
            isinstance(
                memory["rank"],
                int,
            )
            and memory["rank"] <= 3
        )

        if (
            base_success
            != memory_success
        ):

            comparison[
                "case_changes"
            ].append(
                {
                    "id":
                        base["id"],

                    "target":
                        base["target"],

                    "bci_input":
                        base[
                            "bci_input"
                        ],

                    "base":
                        base[
                            "predictions"
                        ],

                    "base_rank":
                        base["rank"],

                    "memory":
                        memory[
                            "predictions"
                        ],

                    "memory_rank":
                        memory[
                            "rank"
                        ],

                    "change":
                        (
                            "improved"
                            if memory_success
                            else "regressed"
                        ),
                }
            )

    REPORT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT.write_text(
        json.dumps(
            comparison,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "=" * 70
    )

    print(
        "FINAL COMPARISON"
    )

    print(
        "=" * 70
    )

    print(
        json.dumps(
            comparison[
                "delta"
            ],
            ensure_ascii=False,
            indent=2,
        )
    )

    print()
    print(
        "BASE:",
        base_summary,
    )

    print(
        "V7 MEMORY:",
        memory_summary,
    )

    print()
    print(
        "REPORT:",
        REPORT,
    )


if __name__ == "__main__":
    main()
