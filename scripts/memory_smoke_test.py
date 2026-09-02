from __future__ import annotations

from app.llm.memory_augmented_client import (
    MemoryAugmentedLanguageModelClient,
)


CASES = [
    "ㅁㅈ",
    "ㄷㅇㅈ",
    "ㅈㅇ",
    "ㅇㄴ",
    "ㅁㅇ",
    "ㅂㅈ",
    "ㅅㅇ",
    "ㄷㅇ",
    "ㄱㅁㅇ",
]


def main():

    client = (
        MemoryAugmentedLanguageModelClient()
    )

    print(
        "Memory phrases:",
        client.memory.total_phrases(),
    )

    print(
        "Memory groups:",
        client.memory.total_groups(),
    )

    for initials in CASES:

        print()
        print("=" * 70)

        print(
            "INPUT:",
            initials
        )

        print(
            "MEMORY:",
            client.memory.candidates(
                initials,
                8,
            )
        )

        result = (
            client.generate_candidates(
                initials,
                16,
            )
        )

        print(
            "MERGED:",
            result.candidates
        )


if __name__ == "__main__":
    main()