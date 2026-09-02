from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable

CHO = [
    "ㄱ","ㄲ","ㄴ","ㄷ","ㄸ","ㄹ","ㅁ","ㅂ","ㅃ","ㅅ",
    "ㅆ","ㅇ","ㅈ","ㅉ","ㅊ","ㅋ","ㅌ","ㅍ","ㅎ"
]
PUNCT_RE = re.compile(r"""[.,!?~…'"“”‘’·:;()\[\]{}<>]""")


def extract_initials(text: str) -> str:
    out: list[str] = []
    for ch in unicodedata.normalize("NFC", text or ""):
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            out.append(CHO[(code - 0xAC00) // 588])
        elif ch in CHO:
            out.append(ch)
    return "".join(out)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").strip()
    text = re.sub(r"\s+", "", text)
    text = PUNCT_RE.sub("", text)
    return text


def read_jsonl(path: str | Path) -> list[dict]:
    path = Path(path)
    rows: list[dict] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"{path}:{line_no}: {exc}") from exc
    return rows


def write_jsonl(path: str | Path, rows: Iterable[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def unique_normalized(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        item = str(item).strip()
        key = normalize_text(item)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
