from __future__ import annotations

import json
import threading
from pathlib import Path

from app.config import ROOT_DIR

_DEFAULT_PATH = ROOT_DIR / "data" / "habitual_phrases.json"


class HabitualPhraseStore:
    """Durable, file-backed '익숙하게 쓰는 문장' (habitual phrase) counter.

    Every time a candidate is committed in a session (see
    app/api/session.py's select_candidate), it is also recorded here, keyed
    by (partner, situation, text). This lets the speller offer instant
    one-tap access to phrases the person actually uses often -- the fastest
    possible interaction is not generating a better candidate, it's not
    needing to generate one at all.

    Deliberately a flat JSON file rather than a database: this is a
    single-process research prototype (see InMemorySessionManager's own
    docstring for the same caveat about production-readiness), and a JSON
    file is trivial to inspect, back up, or reset by hand during a demo.
    """

    def __init__(self, path: Path | str = _DEFAULT_PATH) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._data: dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._data = {}
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._data = {str(k): int(v) for k, v in raw.items() if str(k).strip()}
        except Exception:
            self._data = {}

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError:
            # Best-effort persistence only: a failed write must never break
            # the speller's core select/commit flow.
            pass

    @staticmethod
    def _key(partner: str, situation: str, text: str) -> str:
        return f"{partner}␟{situation}␟{text}"

    def record(self, partner: str, situation: str, text: str) -> None:
        text = text.strip()
        if not text:
            return
        with self._lock:
            key = self._key(partner, situation, text)
            self._data[key] = self._data.get(key, 0) + 1
            self._save()

    def top(
        self,
        *,
        partner: str | None = None,
        situation: str | None = None,
        limit: int = 6,
    ) -> list[tuple[str, int]]:
        with self._lock:
            totals: dict[str, int] = {}
            for key, count in self._data.items():
                parts = key.split("␟")
                if len(parts) != 3:
                    continue
                k_partner, k_situation, text = parts
                if partner is not None and k_partner != partner:
                    continue
                if situation is not None and k_situation != situation:
                    continue
                totals[text] = totals.get(text, 0) + count
            ranked = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
            return ranked[:limit]

    def top_tiered(self, *, partner: str, situation: str, limit: int = 6) -> list[tuple[str, int]]:
        """Most relevant first: same partner+situation, then same partner
        only, then globally -- so a brand-new (partner, situation) pair
        still surfaces the person's overall habitual phrases instead of an
        empty list."""
        tiers = (
            {"partner": partner, "situation": situation},
            {"partner": partner, "situation": None},
            {"partner": None, "situation": None},
        )
        seen: set[str] = set()
        result: list[tuple[str, int]] = []
        for tier in tiers:
            if len(result) >= limit:
                break
            for text, count in self.top(limit=limit * 3, **tier):
                if text in seen:
                    continue
                seen.add(text)
                result.append((text, count))
                if len(result) >= limit:
                    break
        return result


habitual_store = HabitualPhraseStore()
