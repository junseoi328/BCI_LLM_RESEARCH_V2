from __future__ import annotations

import sys

import torch


def main() -> int:

    print("=" * 70)
    print("LOCAL FINE-TUNING ENVIRONMENT")
    print("=" * 70)

    print("Python:", sys.version)
    print("PyTorch:", torch.__version__)

    print(
        "CUDA available:",
        torch.cuda.is_available(),
    )

    if not torch.cuda.is_available():

        print()
        print("CUDA GPU를 찾지 못했습니다.")
        print(
            "3B QLoRA 학습은 NVIDIA CUDA GPU에서 "
            "실행하는 것을 권장합니다."
        )

        return 2

    count = torch.cuda.device_count()

    print("GPU count:", count)

    for i in range(count):

        props = (
            torch.cuda
            .get_device_properties(i)
        )

        memory_gb = (
            props.total_memory
            / 1024**3
        )

        print()
        print(
            f"GPU {i}:",
            props.name,
        )

        print(
            "VRAM:",
            f"{memory_gb:.2f} GB",
        )

    print()

    print(
        "BF16 support:",
        torch.cuda.is_bf16_supported(),
    )

    print()
    print("ENVIRONMENT OK")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
