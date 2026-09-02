from __future__ import annotations

from pathlib import Path

from huggingface_hub import snapshot_download


MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"

OUTPUT = Path(
    "local_models/base/"
    "Qwen2.5-0.5B-Instruct"
)


def main():

    OUTPUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 70)
    print("BCI BASE MODEL DOWNLOAD")
    print("=" * 70)

    print("MODEL :", MODEL_ID)
    print("OUTPUT:", OUTPUT)

    path = snapshot_download(

        repo_id=MODEL_ID,

        local_dir=str(OUTPUT),

        resume_download=True,
    )

    print()
    print("=" * 70)
    print("DOWNLOAD COMPLETE")
    print("=" * 70)

    print(path)


if __name__ == "__main__":
    main()