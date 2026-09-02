from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY가 없습니다.")

    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    jobs = client.fine_tuning.jobs.list(limit=20)

    print("OpenAI Fine-tuning Dashboard:")
    print("https://platform.openai.com/finetune")
    print()
    for job in jobs.data:
        print(
            f"{job.id}  status={job.status}  base={job.model}  "
            f"ft={getattr(job, 'fine_tuned_model', None)}"
        )


if __name__ == "__main__":
    main()
