from __future__ import annotations

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


JOB_STATE = Path(
    "training_v2/artifacts/"
    "ft_job_v2.json"
)

MODEL_STATE = Path(
    "training_v2/artifacts/"
    "ft_model_v2.json"
)

UNAVAILABLE_STATE = Path(
    "training_v2/artifacts/"
    "fine_tuning_unavailable.json"
)

TERMINAL = {
    "succeeded",
    "failed",
    "cancelled",
}


def main() -> int:

    # --------------------------------------------------
    # 1. Fine-tuning job 자체가 존재하는지 확인
    # --------------------------------------------------

    if not JOB_STATE.exists():

        print("=" * 70)
        print("NO FINE-TUNING JOB")
        print("=" * 70)

        print(
            "ft_job_v2.json이 없습니다."
        )

        print(
            "Fine-tuning job 생성이 "
            "성공하지 않았습니다."
        )

        if UNAVAILABLE_STATE.exists():

            print()
            print(
                "현재 OpenAI organization에서 "
                "새 Fine-tuning job 생성이 "
                "지원되지 않는 상태입니다."
            )

            print()

            try:

                unavailable = json.loads(
                    UNAVAILABLE_STATE.read_text(
                        encoding="utf-8"
                    )
                )

                print(
                    "reason:",
                    unavailable.get(
                        "reason"
                    )
                )

            except Exception:
                pass

        return 2

    # --------------------------------------------------
    # 2. API KEY 확인
    # --------------------------------------------------

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:

        print(
            "ERROR: OPENAI_API_KEY 없음"
        )

        return 3

    # --------------------------------------------------
    # 3. Job state 읽기
    # --------------------------------------------------

    try:

        state = json.loads(
            JOB_STATE.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:

        print(
            "ERROR: ft_job_v2.json "
            "읽기 실패"
        )

        print(
            type(exc).__name__,
            exc
        )

        return 4

    job_id = state.get(
        "job_id"
    )

    if not job_id:

        print(
            "ERROR: job_id 없음"
        )

        return 5

    # --------------------------------------------------
    # 4. OpenAI client
    # --------------------------------------------------

    client = OpenAI(
        api_key=api_key
    )

    previous_status = None

    print("=" * 70)
    print("WATCH FINE-TUNING JOB")
    print("=" * 70)

    print(
        "JOB ID:",
        job_id
    )

    # --------------------------------------------------
    # 5. Polling
    # --------------------------------------------------

    while True:

        try:

            job = (
                client
                .fine_tuning
                .jobs
                .retrieve(
                    job_id
                )
            )

        except Exception as exc:

            print()
            print(
                "Fine-tuning job 조회 실패"
            )

            print(
                type(exc).__name__,
                exc
            )

            return 6

        # 상태가 변경됐을 때만 출력
        if (
            job.status
            != previous_status
        ):

            print()
            print(
                "STATUS:",
                job.status,
            )

            print(
                "MODEL:",
                getattr(
                    job,
                    "fine_tuned_model",
                    None,
                ),
            )

            previous_status = (
                job.status
            )

        # --------------------------------------------------
        # 6. 완료 상태
        # --------------------------------------------------

        if job.status in TERMINAL:

            result = {

                "job_id":
                    job.id,

                "status":
                    job.status,

                "base_model":
                    getattr(
                        job,
                        "model",
                        None,
                    ),

                "fine_tuned_model":
                    getattr(
                        job,
                        "fine_tuned_model",
                        None,
                    ),

                "trained_tokens":
                    getattr(
                        job,
                        "trained_tokens",
                        None,
                    ),

                "result_files":
                    list(
                        getattr(
                            job,
                            "result_files",
                            [],
                        )
                        or []
                    ),
            }

            MODEL_STATE.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            MODEL_STATE.write_text(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            print()
            print("=" * 70)
            print("FINAL RESULT")
            print("=" * 70)

            print(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )

            print()
            print(
                "Saved:",
                MODEL_STATE
            )

            if (
                job.status
                == "succeeded"
            ):

                print()
                print(
                    "FINE-TUNING SUCCEEDED"
                )

                print(
                    "Fine-tuned model:"
                )

                print(
                    getattr(
                        job,
                        "fine_tuned_model",
                        None,
                    )
                )

                return 0

            print()
            print(
                "FINE-TUNING DID NOT SUCCEED"
            )

            return 7

        # --------------------------------------------------
        # 7. 30초 대기
        # --------------------------------------------------

        time.sleep(30)


if __name__ == "__main__":
    raise SystemExit(main())