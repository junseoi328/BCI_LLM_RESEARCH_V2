import csv
import re
import unicodedata
from pathlib import Path
from statistics import mean, median


# ============================================================
# 비교할 CSV
# ============================================================

V2_FILE = Path(
    r"eval\reports\eval_full_20260831_033638.csv"
)

V4_FILE = Path(
    r"eval\reports\eval_full_20260831_042045.csv"
)


# ============================================================
# 평가용 normalization
# ============================================================

def normalize_eval_text(text: str) -> str:
    """
    의미는 바꾸지 않고 표면적인 차이만 제거한다.

    예:
        "물 마실래?" -> "물마실래"
        "티비 켜 줘" -> "티비켜줘"
        "맞아."      -> "맞아"

    제거:
    - 공백
    - 일반 문장부호
    - Unicode 표현 차이
    """
    if text is None:
        return ""

    text = unicodedata.normalize("NFC", str(text))
    text = text.strip()

    # whitespace 제거
    text = re.sub(r"\s+", "", text)

    # punctuation 제거
    text = re.sub(
        r"""[.,!?~…'"“”‘’·:;()\[\]{}<>]""",
        "",
        text,
    )

    return text


# ============================================================
# CSV 읽기
# ============================================================

def load_csv(path: Path):
    rows = []

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:
            rows.append(row)

    return rows


# ============================================================
# Rank 계산
# ============================================================

def get_predictions(row):
    return [
        row.get("pred_1", "") or "",
        row.get("pred_2", "") or "",
        row.get("pred_3", "") or "",
    ]


def strict_rank(target, predictions):
    target = (target or "").strip()

    for i, pred in enumerate(predictions, start=1):
        if (pred or "").strip() == target:
            return i

    return None


def normalized_rank(target, predictions):
    target_norm = normalize_eval_text(target)

    for i, pred in enumerate(predictions, start=1):
        if normalize_eval_text(pred) == target_norm:
            return i

    return None


# ============================================================
# Metric 계산
# ============================================================

def reciprocal_rank(rank):
    if rank is None:
        return 0.0

    return 1.0 / rank


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate(rows):
    strict_ranks = []
    normalized_ranks = []

    latencies = []
    costs = []

    fallback_count = 0
    service_errors = 0

    case_results = []

    for row in rows:

        target = row["target"]
        predictions = get_predictions(row)

        s_rank = strict_rank(
            target,
            predictions,
        )

        n_rank = normalized_rank(
            target,
            predictions,
        )

        strict_ranks.append(s_rank)
        normalized_ranks.append(n_rank)

        latency = safe_float(
            row.get("latency_ms")
        )

        if latency is not None:
            latencies.append(latency)

        cost = safe_float(
            row.get("estimated_cost_usd")
        )

        if cost is not None:
            costs.append(cost)

        fallback = (
            row.get("fallback", "")
            or ""
        ).strip().lower()

        if fallback not in (
            "",
            "none",
            "false",
            "0",
        ):
            fallback_count += 1

        service_error = (
            row.get("service_error_code", "")
            or ""
        ).strip()

        if service_error:
            service_errors += 1

        case_results.append({
            "id": row.get("id"),
            "input": row.get("bci_input"),
            "target": target,
            "predictions": predictions,
            "strict_rank": s_rank,
            "normalized_rank": n_rank,
        })

    n = len(rows)

    strict_acc1 = sum(
        r == 1 for r in strict_ranks
    ) / n

    strict_acc3 = sum(
        r is not None and r <= 3
        for r in strict_ranks
    ) / n

    normalized_acc1 = sum(
        r == 1 for r in normalized_ranks
    ) / n

    normalized_acc3 = sum(
        r is not None and r <= 3
        for r in normalized_ranks
    ) / n

    strict_mrr = mean(
        reciprocal_rank(r)
        for r in strict_ranks
    )

    normalized_mrr = mean(
        reciprocal_rank(r)
        for r in normalized_ranks
    )

    return {
        "n": n,

        "strict_acc1": strict_acc1,
        "strict_acc3": strict_acc3,
        "strict_mrr": strict_mrr,

        "normalized_acc1": normalized_acc1,
        "normalized_acc3": normalized_acc3,
        "normalized_mrr": normalized_mrr,

        "mean_latency_ms":
            mean(latencies)
            if latencies else None,

        "median_latency_ms":
            median(latencies)
            if latencies else None,

        "total_cost_usd":
            sum(costs),

        "mean_cost_usd":
            mean(costs)
            if costs else None,

        "fallback_rate":
            fallback_count / n,

        "service_error_rate":
            service_errors / n,

        "cases": case_results,
    }


# ============================================================
# 출력
# ============================================================

def print_summary(name, result):

    print()
    print("=" * 70)
    print(name)
    print("=" * 70)

    print(f"N                    : {result['n']}")

    print()
    print("[STRICT]")
    print(
        f"Acc@1                : "
        f"{result['strict_acc1']:.3f}"
    )
    print(
        f"Acc@3                : "
        f"{result['strict_acc3']:.3f}"
    )
    print(
        f"MRR                  : "
        f"{result['strict_mrr']:.3f}"
    )

    print()
    print("[NORMALIZED]")
    print(
        f"Acc@1                : "
        f"{result['normalized_acc1']:.3f}"
    )
    print(
        f"Acc@3                : "
        f"{result['normalized_acc3']:.3f}"
    )
    print(
        f"MRR                  : "
        f"{result['normalized_mrr']:.3f}"
    )

    print()
    print("[SYSTEM]")
    print(
        f"Mean latency         : "
        f"{result['mean_latency_ms']:.1f} ms"
    )
    print(
        f"Median latency       : "
        f"{result['median_latency_ms']:.1f} ms"
    )
    print(
        f"Fallback rate        : "
        f"{result['fallback_rate']:.3f}"
    )
    print(
        f"Service error rate   : "
        f"{result['service_error_rate']:.3f}"
    )
    print(
        f"Total estimated cost : "
        f"${result['total_cost_usd']:.6f}"
    )
    print(
        f"Mean cost / request  : "
        f"${result['mean_cost_usd']:.6f}"
    )


# ============================================================
# 버전별 case 비교
# ============================================================

def compare_cases(v2, v4):

    v2_map = {
        c["id"]: c
        for c in v2["cases"]
    }

    v4_map = {
        c["id"]: c
        for c in v4["cases"]
    }

    improved = []
    regressed = []
    unchanged_success = []
    unchanged_failure = []

    for case_id in v2_map.keys():

        if case_id not in v4_map:
            continue

        a = v2_map[case_id]
        b = v4_map[case_id]

        a_ok = (
            a["normalized_rank"]
            is not None
        )

        b_ok = (
            b["normalized_rank"]
            is not None
        )

        if not a_ok and b_ok:
            improved.append((a, b))

        elif a_ok and not b_ok:
            regressed.append((a, b))

        elif a_ok and b_ok:
            unchanged_success.append((a, b))

        else:
            unchanged_failure.append((a, b))

    print()
    print("=" * 70)
    print("V2 -> V4 CASE CHANGES (NORMALIZED)")
    print("=" * 70)

    print(
        f"Improved          : {len(improved)}"
    )
    print(
        f"Regressed         : {len(regressed)}"
    )
    print(
        f"Both success      : {len(unchanged_success)}"
    )
    print(
        f"Both failure      : {len(unchanged_failure)}"
    )

    print()
    print("--- IMPROVED ---")

    for old, new in improved:
        print(
            f"{old['id']} "
            f"{old['input']} "
            f"target={old['target']!r}"
        )

        print(
            f"    V2: {old['predictions']}"
        )

        print(
            f"    V4: {new['predictions']} "
            f"rank={new['normalized_rank']}"
        )

    print()
    print("--- REGRESSED ---")

    for old, new in regressed:
        print(
            f"{old['id']} "
            f"{old['input']} "
            f"target={old['target']!r}"
        )

        print(
            f"    V2: {old['predictions']} "
            f"rank={old['normalized_rank']}"
        )

        print(
            f"    V4: {new['predictions']}"
        )


# ============================================================
# Main
# ============================================================

def main():

    if not V2_FILE.exists():
        raise FileNotFoundError(
            f"V2 CSV not found: {V2_FILE}"
        )

    if not V4_FILE.exists():
        raise FileNotFoundError(
            f"V4 CSV not found: {V4_FILE}"
        )

    v2_rows = load_csv(V2_FILE)
    v4_rows = load_csv(V4_FILE)

    v2_result = evaluate(v2_rows)
    v4_result = evaluate(v4_rows)

    print_summary(
        "GENERATOR V2",
        v2_result,
    )

    print_summary(
        "GENERATOR V4",
        v4_result,
    )

    print()
    print("=" * 70)
    print("DELTA: V4 - V2")
    print("=" * 70)

    print(
        f"Strict Acc@1       : "
        f"{v4_result['strict_acc1'] - v2_result['strict_acc1']:+.3f}"
    )

    print(
        f"Strict Acc@3       : "
        f"{v4_result['strict_acc3'] - v2_result['strict_acc3']:+.3f}"
    )

    print(
        f"Normalized Acc@1   : "
        f"{v4_result['normalized_acc1'] - v2_result['normalized_acc1']:+.3f}"
    )

    print(
        f"Normalized Acc@3   : "
        f"{v4_result['normalized_acc3'] - v2_result['normalized_acc3']:+.3f}"
    )

    print(
        f"Mean latency       : "
        f"{v4_result['mean_latency_ms'] - v2_result['mean_latency_ms']:+.1f} ms"
    )

    print(
        f"Fallback rate      : "
        f"{v4_result['fallback_rate'] - v2_result['fallback_rate']:+.3f}"
    )

    print(
        f"Total cost         : "
        f"${v4_result['total_cost_usd'] - v2_result['total_cost_usd']:+.6f}"
    )

    compare_cases(
        v2_result,
        v4_result,
    )


if __name__ == "__main__":
    main()