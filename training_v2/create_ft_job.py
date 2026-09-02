from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from openai import PermissionDeniedError


load_dotenv()


UPLOAD_STATE = Path(
    "training_v2/artifacts/uploaded_files_v2.json"
)

JOB_STATE = Path(
    "training_v2/artifacts/ft_job_v2.json"
)

UNAVAILABLE_STATE = Path(
    "training_v2/artifacts/"
    "fine_tuning_unavailable.json"
)

BASE_MODEL = "gpt-4.1-mini-2025-04-14"


def main() -> int:

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:

        print("ERROR: OPENAI_API_KEY 없음")

        return 1

    if not UPLOAD_STATE.exists():

        print(
            "ERROR:",
            UPLOAD_STATE,
            "없음"
        )

        return 2

    upload = json.loads(
        UPLOAD_STATE.read_text(
            encoding="utf-8"
        )
    )

    client = OpenAI(
        api_key=api_key
    )

    print(
        "Creating OpenAI fine-tuning job..."
    )

    try:

        job = client.fine_tuning.jobs.create(

            training_file=
                upload[
                    "training_file_id"
                ],

            validation_file=
                upload[
                    "validation_file_id"
                ],

            model=BASE_MODEL,

            suffix=
                "bci-generator-v7-v2",
        )

    except PermissionDeniedError as exc:

        print()
        print("=" * 70)
        print("OPENAI FINE-TUNING NOT AVAILABLE")
        print("=" * 70)

        print(
            "현재 OpenAI organization은 "
            "새 Fine-tuning job을 만들 수 없습니다."
        )

        print()

        print(
            "HTTP status:",
            getattr(
                exc,
                "status_code",
                403
            ),
        )

        print(
            "Error:",
            str(exc)
        )

        state = {

            "available": False,

            "reason":
                "training_not_available",

            "base_model":
                BASE_MODEL,

            "training_file_id":
                upload[
                    "training_file_id"
                ],

            "validation_file_id":
                upload[
                    "validation_file_id"
                ],
        }

        UNAVAILABLE_STATE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        UNAVAILABLE_STATE.write_text(

            json.dumps(
                state,
                ensure_ascii=False,
                indent=2,
            ),

            encoding="utf-8",
        )

        print()
        print(
            "Saved:",
            UNAVAILABLE_STATE
        )

        print()
        print(
            "SFT data itself is still valid."
        )

        return 10

    state = {

        "job_id":
            job.id,

        "status":
            job.status,

        "base_model":
            BASE_MODEL,

        "fine_tuned_model":
            getattr(
                job,
                "fine_tuned_model",
                None,
            ),
    }

    JOB_STATE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    JOB_STATE.write_text(

        json.dumps(
            state,
            ensure_ascii=False,
            indent=2,
        ),

        encoding="utf-8",
    )

    print()
    print("JOB ID:", job.id)
    print("STATUS:", job.status)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())