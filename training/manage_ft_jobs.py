from __future__ import annotations

import argparse
import os

from training_v2.common import load_dotenv_if_available


def main() -> None:
    load_dotenv_if_available()
    p = argparse.ArgumentParser()
    p.add_argument("--cancel", default=None)
    args = p.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY가 없습니다.")

    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    if args.cancel:
        job = client.fine_tuning.jobs.cancel(args.cancel)
        print("CANCELLED:", job.id, job.status)
        return

    jobs = client.fine_tuning.jobs.list(limit=20)
    print("Dashboard: https://platform.openai.com/finetune")
    for job in jobs.data:
        print(
            f"{job.id} status={job.status} model={job.model} "
            f"ft={getattr(job, 'fine_tuned_model', None)}"
        )


if __name__ == "__main__":
    main()
