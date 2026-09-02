from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import statistics
import time
import unicodedata
from pathlib import Path
from typing import Any

from app.config import settings
from app.pipeline.service import BCILanguagePipeline
from app.schemas import PredictionRequest


TRANSIENT_CODES = {
    "connection_error",
    "timeout",
    "rate_limit",
    "service_unavailable",
    "api_connection_error",
    "api_timeout",
}

NONRETRYABLE_CODES = {
    "insufficient_quota",
    "credit_balance_exhausted",
    "invalid_api_key",
    "authentication_error",
}


def normalize_eval_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").strip()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"""[.,!?~…'"“”‘’·:;()\[\]{}<>]""", "", text)
    return text


def rank_of(target: str, preds: list[str], normalized: bool = False) -> int | None:
    if normalized:
        target_cmp = normalize_eval_text(target)
        values = [normalize_eval_text(x) for x in preds]
    else:
        target_cmp = target
        values = preds

    for i, value in enumerate(values, start=1):
        if value == target_cmp:
            return i
    return None


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return float(xs[0])
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(xs[lo])
    return float(xs[lo] + (xs[hi] - xs[lo]) * (pos - lo))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"{path}:{line_no} JSON 오류: {exc}") from exc
            rows.append(obj)
    return rows


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)


def atomic_write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "category",
        "target",
        "bci_input",
        "partner",
        "situation",
        "pred_1",
        "pred_2",
        "pred_3",
        "strict_rank",
        "normalized_rank",
        "latency_ms",
        "fallback",
        "service_error",
        "error_code",
        "attempts",
        "estimated_cost_usd",
        "warnings",
    ]
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
    tmp.replace(path)


def snapshot_config() -> dict[str, Any]:
    return {
        "generator_model": getattr(settings, "generator_model", None),
        "ranker_model": getattr(settings, "ranker_model", None),
        "generation_count": getattr(settings, "generation_count", None),
        "pipeline_version": getattr(settings, "pipeline_version", None),
        "generator_prompt_version": getattr(settings, "generator_prompt_version", None),
        "ranker_prompt_version": getattr(settings, "ranker_prompt_version", None),
        "ensemble_mode": os.getenv("ENSEMBLE_MODE"),
        "ensemble_min_valid": os.getenv("ENSEMBLE_MIN_VALID"),
        "ensemble_max_first_token_ratio": os.getenv("ENSEMBLE_MAX_FIRST_TOKEN_RATIO"),
        "ensemble_context_threshold": os.getenv("ENSEMBLE_CONTEXT_THRESHOLD"),
        "ensemble_intent_threshold": os.getenv("ENSEMBLE_INTENT_THRESHOLD"),
        "diversity_generation_count": os.getenv("DIVERSITY_GENERATION_COUNT"),
        "mock_mode": os.getenv("MOCK_MODE"),
    }


def warning_error_code(warnings: list[str]) -> str | None:
    for warning in warnings:
        low = warning.lower()
        for code in NONRETRYABLE_CODES:
            if code in low:
                return code
        for code in TRANSIENT_CODES:
            if code in low:
                return code
    return None


def exception_code(exc: Exception) -> tuple[str, bool]:
    code = str(getattr(exc, "code", "") or "").lower()
    text = f"{exc.__class__.__name__}: {exc}".lower()

    for value in NONRETRYABLE_CODES:
        if value in code or value in text:
            return value, False

    for value in TRANSIENT_CODES:
        if value in code or value in text:
            return value, True

    cls = exc.__class__.__name__.lower()
    if "connection" in cls:
        return "connection_error", True
    if "timeout" in cls:
        return "timeout", True
    if "ratelimit" in cls or "rate_limit" in cls:
        return "rate_limit", True

    return cls or "unknown_error", False


def build_request(case: dict[str, Any]) -> PredictionRequest:
    return PredictionRequest(
        input_mode=case.get("input_mode", "initials"),
        bci_input=case["bci_input"],
        partner=case.get("partner", "other"),
        situation=case.get("situation", "general"),
        current_sentence=case.get("current_sentence", ""),
        recent_context=case.get("recent_context", []),
        top_k=int(case.get("top_k", 3)),
    )


def response_to_row(
    case: dict[str, Any],
    res: Any,
    attempts: int,
) -> dict[str, Any]:
    preds = [x.text for x in res.candidates]
    while len(preds) < 3:
        preds.append("")

    strict_rank = rank_of(case["target"], preds, normalized=False)
    norm_rank = rank_of(case["target"], preds, normalized=True)

    warnings = list(getattr(res, "warnings", []) or [])
    warning_code = warning_error_code(warnings)

    usage = getattr(res, "usage", None)
    cost = getattr(usage, "estimated_cost_usd", None) if usage else None

    return {
        "id": case["id"],
        "category": case.get("category", ""),
        "target": case["target"],
        "bci_input": case["bci_input"],
        "partner": case.get("partner", ""),
        "situation": case.get("situation", ""),
        "pred_1": preds[0],
        "pred_2": preds[1],
        "pred_3": preds[2],
        "strict_rank": strict_rank,
        "normalized_rank": norm_rank,
        "latency_ms": getattr(getattr(res, "latency", None), "total_ms", None),
        "fallback": getattr(res, "fallback", None),
        "service_error": bool(warning_code),
        "error_code": warning_code,
        "attempts": attempts,
        "estimated_cost_usd": cost,
        "warnings": " | ".join(warnings),
    }


def error_row(case: dict[str, Any], code: str, attempts: int, message: str) -> dict[str, Any]:
    return {
        "id": case["id"],
        "category": case.get("category", ""),
        "target": case["target"],
        "bci_input": case["bci_input"],
        "partner": case.get("partner", ""),
        "situation": case.get("situation", ""),
        "pred_1": "",
        "pred_2": "",
        "pred_3": "",
        "strict_rank": None,
        "normalized_rank": None,
        "latency_ms": None,
        "fallback": None,
        "service_error": True,
        "error_code": code,
        "attempts": attempts,
        "estimated_cost_usd": None,
        "warnings": message,
    }


def summarize(rows: list[dict[str, Any]], label: str, dataset: str) -> dict[str, Any]:
    n = len(rows)
    errors = [r for r in rows if r.get("service_error")]
    ok = [r for r in rows if not r.get("service_error")]

    strict1 = sum(r.get("strict_rank") == 1 for r in rows) / n if n else 0
    strict3 = sum(
        isinstance(r.get("strict_rank"), int) and r["strict_rank"] <= 3
        for r in rows
    ) / n if n else 0
    norm1 = sum(r.get("normalized_rank") == 1 for r in rows) / n if n else 0
    norm3 = sum(
        isinstance(r.get("normalized_rank"), int) and r["normalized_rank"] <= 3
        for r in rows
    ) / n if n else 0

    rr = [
        1 / r["normalized_rank"]
        for r in rows
        if isinstance(r.get("normalized_rank"), int) and r["normalized_rank"] > 0
    ]
    norm_mrr = sum(rr) / n if n else 0

    latencies = [
        float(r["latency_ms"])
        for r in ok
        if r.get("latency_ms") is not None
    ]
    costs = [
        float(r["estimated_cost_usd"])
        for r in ok
        if r.get("estimated_cost_usd") is not None
    ]
    fallback_count = sum(
        bool(r.get("fallback")) and r.get("fallback") != "none"
        for r in ok
    )

    return {
        "label": label,
        "dataset": dataset,
        "n": n,
        "successful_cases": len(ok),
        "service_error_count": len(errors),
        "service_error_rate": len(errors) / n if n else 0,
        "valid_for_reporting": len(errors) == 0,
        "strict_acc_at_1": strict1,
        "strict_acc_at_3": strict3,
        "normalized_acc_at_1": norm1,
        "normalized_acc_at_3": norm3,
        "normalized_mrr": norm_mrr,
        "mean_latency_ms": statistics.mean(latencies) if latencies else None,
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "total_estimated_cost_usd": sum(costs) if costs else 0.0,
        "mean_estimated_cost_usd": statistics.mean(costs) if costs else None,
        "fallback_rate_successful_cases": fallback_count / len(ok) if ok else None,
        "config": snapshot_config(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=r"eval\datasets\test_v1_150.jsonl")
    parser.add_argument("--label", required=True)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--between-cases", type=float, default=1.0)
    parser.add_argument("--retry-base-sec", type=float, default=3.0)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    cases = load_jsonl(dataset_path)
    if args.limit is not None:
        cases = cases[: args.limit]

    checkpoint_dir = Path("eval") / "checkpoints"
    report_dir = Path("eval") / "reports"
    checkpoint_path = checkpoint_dir / f"{args.label}.checkpoint.json"
    csv_path = report_dir / f"{args.label}.csv"
    summary_path = report_dir / f"{args.label}.summary.json"

    checkpoint: dict[str, Any] = {
        "label": args.label,
        "dataset": str(dataset_path),
        "config": snapshot_config(),
        "rows": {},
    }
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    saved_rows: dict[str, dict[str, Any]] = checkpoint.setdefault("rows", {})

    pipeline = BCILanguagePipeline()
    total = len(cases)

    for index, case in enumerate(cases, start=1):
        case_id = case["id"]
        old = saved_rows.get(case_id)

        # 성공한 케이스만 skip. 실패 케이스는 재실행 시 자동 재시도.
        if old and not old.get("service_error", False):
            print(
                f"[{index:03d}/{total:03d}] {case_id} SKIP(success) "
                f"target={case['target']} preds="
                f"{[old.get('pred_1'), old.get('pred_2'), old.get('pred_3')]}"
            )
            continue

        req = build_request(case)
        final_row: dict[str, Any] | None = None

        for attempt in range(1, args.max_retries + 2):
            try:
                res = pipeline.predict(req)
                row = response_to_row(case, res, attempt)

                # 파이프라인이 fallback으로 숨긴 일시적 API 오류도 재시도.
                if row["service_error"]:
                    code = row["error_code"] or "service_error"
                    retryable = code in TRANSIENT_CODES
                    if not retryable:
                        final_row = row
                        break

                    if attempt <= args.max_retries:
                        wait = args.retry_base_sec * (2 ** (attempt - 1))
                        print(
                            f"[{index:03d}/{total:03d}] {case_id} "
                            f"{code} -> retry {attempt}/{args.max_retries} "
                            f"after {wait:.1f}s"
                        )
                        time.sleep(wait)
                        continue

                    final_row = row
                    break

                final_row = row
                break

            except Exception as exc:
                code, retryable = exception_code(exc)

                if retryable and attempt <= args.max_retries:
                    wait = args.retry_base_sec * (2 ** (attempt - 1))
                    print(
                        f"[{index:03d}/{total:03d}] {case_id} "
                        f"{code} -> retry {attempt}/{args.max_retries} "
                        f"after {wait:.1f}s"
                    )
                    time.sleep(wait)
                    continue

                final_row = error_row(
                    case,
                    code=code,
                    attempts=attempt,
                    message=f"{exc.__class__.__name__}: {exc}",
                )
                break

        assert final_row is not None
        saved_rows[case_id] = final_row
        checkpoint["config"] = snapshot_config()
        atomic_write_json(checkpoint_path, checkpoint)

        ordered = [saved_rows[c["id"]] for c in cases if c["id"] in saved_rows]
        atomic_write_csv(csv_path, ordered)

        print(
            f"[{index:03d}/{total:03d}] {case['bci_input']} "
            f"target={case['target']} "
            f"preds={[final_row.get('pred_1'), final_row.get('pred_2'), final_row.get('pred_3')]} "
            f"norm_rank={final_row.get('normalized_rank')} "
            f"latency={final_row.get('latency_ms')}ms "
            f"error={final_row.get('error_code')}"
        )

        if args.between_cases > 0:
            time.sleep(args.between_cases)

    ordered = [saved_rows[c["id"]] for c in cases if c["id"] in saved_rows]
    atomic_write_csv(csv_path, ordered)
    summary = summarize(ordered, args.label, str(dataset_path))
    atomic_write_json(summary_path, summary)

    print("\n=== RELIABLE TEST SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"CSV: {csv_path}")
    print(f"Checkpoint: {checkpoint_path}")
    print(f"Summary: {summary_path}")

    if summary["service_error_count"] > 0:
        print(
            "\n아직 service error가 남아 있습니다. "
            "같은 명령을 다시 실행하면 성공 케이스는 skip하고 "
            "실패 케이스만 재시도합니다."
        )
        return 2

    print("\nSERVICE ERROR = 0. 이 결과는 성능 비교에 사용할 수 있습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
