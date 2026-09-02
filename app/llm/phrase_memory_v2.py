from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from training_v2.common import (
    extract_initials,
    normalize_text,
)


class PhraseMemoryV2:

    def __init__(
        self,
        path: str | Path = (
            "research/phrase_memory/"
            "approved_bci_phrase_bank_v2.jsonl"
        ),
    ):
        self.path = Path(path)

        self._data: dict[
            str,
            list[dict]
        ] = {}

        self.reload()

    def reload(self) -> None:

        if not self.path.exists():

            raise FileNotFoundError(
                f"Phrase memory 없음: {self.path}"
            )

        grouped = defaultdict(list)

        with self.path.open(
            "r",
            encoding="utf-8-sig",
        ) as f:

            for line_no, line in enumerate(
                f,
                start=1,
            ):

                line = line.strip()

                if not line:
                    continue

                try:

                    row = json.loads(line)

                except Exception as exc:

                    print(
                        f"Phrase memory "
                        f"line {line_no} skip:",
                        exc,
                    )

                    continue

                text = str(
                    row.get("text") or ""
                ).strip()

                initials = str(
                    row.get("initials") or ""
                ).strip()

                if not text or not initials:
                    continue

                # hard constraint
                if (
                    extract_initials(text)
                    != initials
                ):
                    continue

                grouped[
                    initials
                ].append(
                    {
                        "text":
                            text,

                        "weight":
                            float(
                                row.get(
                                    "weight",
                                    1.0,
                                )
                            ),

                        "category":
                            str(
                                row.get(
                                    "category",
                                    "",
                                )
                            ),

                        "source":
                            str(
                                row.get(
                                    "source",
                                    "",
                                )
                            ),
                    }
                )

        output = {}

        for initials, rows in grouped.items():

            # weight 높은 표현 우선
            rows.sort(
                key=lambda x: -x["weight"]
            )

            seen = set()
            clean = []

            for row in rows:

                key = normalize_text(
                    row["text"]
                )

                if key in seen:
                    continue

                seen.add(key)

                clean.append(row)

            output[initials] = clean

        self._data = output

    def candidates(
        self,
        initials: str,
        limit: int = 6,
    ) -> list[str]:

        rows = self._data.get(
            initials,
            [],
        )

        return [
            row["text"]
            for row
            in rows[:limit]
        ]

    def size(
        self,
        initials: str,
    ) -> int:

        return len(
            self._data.get(
                initials,
                [],
            )
        )

    def total_phrases(self) -> int:

        return sum(
            len(v)
            for v
            in self._data.values()
        )

    def total_groups(self) -> int:

        return len(
            self._data
        )