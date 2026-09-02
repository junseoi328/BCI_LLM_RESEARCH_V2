from __future__ import annotations

import json
from pathlib import Path

from training.common import extract_initials, normalize_text, unique_preserve


class PhraseMemory:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._by_initials: dict[str, list[tuple[str, float]]] = {}
        if self.path.exists():
            self.reload()

    def reload(self) -> None:
        by: dict[str, list[tuple[str, float]]] = {}
        with self.path.open("r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                text = str(row["text"]).strip()
                initials = str(row.get("initials") or extract_initials(text))
                weight = float(row.get("weight", 1.0))
                if extract_initials(text) != initials:
                    continue
                by.setdefault(initials, []).append((text, weight))

        for initials, rows in by.items():
            rows.sort(key=lambda x: -x[1])
            deduped: list[tuple[str, float]] = []
            seen: set[str] = set()
            for text, weight in rows:
                key = normalize_text(text)
                if key in seen:
                    continue
                seen.add(key)
                deduped.append((text, weight))
            by[initials] = deduped
        self._by_initials = by

    def candidates(self, initials: str, limit: int = 8) -> list[str]:
        return [x[0] for x in self._by_initials.get(initials, [])[:limit]]
