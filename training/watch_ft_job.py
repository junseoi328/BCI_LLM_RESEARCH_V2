from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from training_v2.common import load_dotenv_if_available

TERMINAL = {"succeeded","failed","cancelled"}


def main() -> int:
    load_dotenv_if_available()
    p = argparse.ArgumentParser()
    p.add_argument("--poll-sec", type=int, default=30)
    p.add_argument("--once", action="store_true")
    args = p.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY가 없습니다.")

    state = json.loads(Path("training_v2/artifacts/ft_job_v2.json").read_text(encoding="utf-8"))
    job_id = state["job_id"]

    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    last = None
    while True:
        job = client.fine_tuning.jobs.retrieve(job_id)
        if job.status != last:
            print(
                f"job={job.id} status={job.status} "
                f"fine_tuned_model={getattr(job, 'fine_tuned_model', None)}"
            )
            last = job.status

        if job.status in TERMINAL:
            result = {
                "job_id": job.id,
                "status": job.status,
                "base_model": getattr(job, "model", None),
                "fine_tuned_model": getattr(job, "fine_tuned_model", None),
                "trained_tokens": getattr(job, "trained_tokens", None),
                "result_files": list(getattr(job, "result_files", []) or []),
            }
            Path("training_v2/artifacts/ft_model_v2.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if job.status == "succeeded" else 2

        if args.once:
            return 0
        time.sleep(max(5, args.poll_sec))


if __name__ == "__main__":
    raise SystemExit(main())
