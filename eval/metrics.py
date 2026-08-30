from __future__ import annotations

import math
from statistics import mean


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - pos) + xs[hi] * (pos - lo)


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {"n": 0}

    ranks = [r.get("target_rank") for r in rows]
    latencies = [float(r.get("latency_ms", 0)) for r in rows]
    costs = [float(r.get("estimated_cost_usd") or 0) for r in rows]

    acc1 = sum(rank == 1 for rank in ranks) / n
    acc3 = sum(rank is not None and rank <= 3 for rank in ranks) / n
    mrr = mean((1 / rank) if rank else 0 for rank in ranks)

    return {
        "n": n,
        "acc_at_1": round(acc1, 4),
        "acc_at_3": round(acc3, 4),
        "mrr": round(mrr, 4),
        "mean_latency_ms": round(mean(latencies), 2),
        "p50_latency_ms": round(percentile(latencies, 0.50), 2),
        "p95_latency_ms": round(percentile(latencies, 0.95), 2),
        "total_estimated_cost_usd": round(sum(costs), 6),
        "mean_estimated_cost_usd": round(mean(costs), 8),
        "fallback_rate": round(sum(bool(r.get("fallback") and r["fallback"] != "none") for r in rows) / n, 4),
    }


def ksr(baseline_selections: float, assisted_selections: float) -> float:
    if baseline_selections <= 0:
        raise ValueError("baseline_selections must be > 0")
    return 1.0 - assisted_selections / baseline_selections



import re
import unicodedata


def normalize_eval_text(text: str) -> str:
    """
    의미를 바꾸지 않는 표면 차이만 제거한다.

    예:
    '물 마실래?' -> '물마실래'
    '티비 켜 줘' -> '티비켜줘'
    '맞아.' -> '맞아'
    """
    text = unicodedata.normalize("NFC", text or "")
    text = text.strip()

    # 공백 제거
    text = re.sub(r"\s+", "", text)

    # 일반 문장부호 제거
    text = re.sub(
        r"""[.,!?~…'"“”‘’·:;()\[\]{}]""",
        "",
        text,
    )

    return text


def normalized_rank(target: str, predictions: list[str]):
    target_norm = normalize_eval_text(target)

    for i, prediction in enumerate(predictions, start=1):
        if normalize_eval_text(prediction) == target_norm:
            return i

    return None
