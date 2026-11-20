"""SSVEP 오프라인 판독 — 앱의 '뇌파+이벤트 CSV'(OpenBCI Cyton)를 CCA로 맞혀 본다.

usage: python tools/ssvep_offline.py 기록.csv [--win 2.0] [--lat 0.14] [--harm 3] [--ch 1,2,3] [--gap 1.5] [--trials]

- 시행 = 이벤트 `stim_on`(정답 키 target, 주파수 f) ~ `stim_off`. 시각 지연 lat 뒤부터 win초.
- 후보 = 기록 당시 화면의 키 주파수(#M table). 각 주파수의 sin·cos 고조파(harm)와 CCA 상관이 가장 큰 키를 고른다.
- ITR(Wolpaw)은 한 번 고르는 데 win+gap초(시선 옮김·쉼)를 쓴다고 보고 계산한다.
ponytail: 필터뱅크(FBCCA)·TRCA 없음 — 보정 데이터가 쌓이면 그때 붙인다. numpy만 쓴다.
"""
import argparse
import json
import math

import numpy as np  # 개발용(requirements.txt) — 서버 배포 이미지에는 없음


def load(path):
    meta, events, rows = {}, [], []
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            if line.startswith("#M "):
                meta = json.loads(line[3:])
            elif line.startswith("#E "):
                events.append(json.loads(line[3:]))
            elif line[:1].isdigit() or line[:1] == "-":
                rows.append([float(x) for x in line.strip().split(",")])
    return meta, events, np.array(rows) if rows else np.zeros((0, 11))


def cca_r(x, y):
    """x: 표본×채널, y: 표본×기준. 가장 큰 정준상관."""
    qx, _ = np.linalg.qr(x - x.mean(0))
    qy, _ = np.linalg.qr(y - y.mean(0))
    return float(np.linalg.svd(qx.T @ qy, compute_uv=False)[0])


def refs(f, t, harm):
    return np.column_stack([fn(2 * math.pi * h * f * t) for h in range(1, harm + 1) for fn in (np.sin, np.cos)])


def trials(events):
    out, cur = [], None
    for e in events:
        if e["type"] == "stim_on" and e.get("target") is not None and e.get("target", -1) >= 0:
            cur = e
        elif e["type"] == "stim_off" and cur is not None:
            if not e.get("aborted"):
                out.append((cur, e))
            cur = None
    return out


def itr(n, p, sec):
    if n < 2 or sec <= 0:
        return 0.0
    p = min(max(p, 1e-9), 1.0)
    bits = math.log2(n) + p * math.log2(p) + ((1 - p) * math.log2((1 - p) / (n - 1)) if p < 1 else 0)
    return max(bits, 0.0) * 60 / sec


def analyze(path, win=2.0, lat=0.14, harm=3, ch=None, gap=1.5):
    meta, events, data = load(path)
    srate = meta.get("srate", 250) or 250
    freqs = sorted({k["f"] for k in meta.get("table", [])}) or [round(8 + 0.2 * i, 1) for i in range(40)]
    cols = [2 + c for c in (ch or range(1, data.shape[1] - 2))]   # t_ms, arrival_ms, sample, ch1..chN (Cyton 8, Ganglion 4)
    res = []
    for on, off in trials(events):
        w = min(win, (off["t"] - on["t"]) / 1000 - lat)
        if w <= 0.2:
            continue
        m = (data[:, 0] >= on["t"] + lat * 1000) & (data[:, 0] < on["t"] + (lat + w) * 1000)
        x = data[m][:, cols]
        if len(x) < srate * 0.2:
            continue
        t = np.arange(len(x)) / srate
        r = [cca_r(x, refs(f, t, harm)) for f in freqs]
        res.append({"target_f": on["f"], "pred_f": freqs[int(np.argmax(r))], "r": max(r), "win": w, "key": on.get("key", "")})
    n_ok = sum(1 for r in res if abs(r["pred_f"] - r["target_f"]) < 1e-6)
    acc = n_ok / len(res) if res else 0.0
    mean_w = float(np.mean([r["win"] for r in res])) if res else 0.0
    return {"trials": len(res), "accuracy": round(acc, 3), "targets": len(freqs), "win_s": round(mean_w, 2),
            "itr_bits_min": round(itr(len(freqs), acc, mean_w + gap), 1), "detail": res}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--win", type=float, default=2.0)
    ap.add_argument("--lat", type=float, default=0.14)
    ap.add_argument("--harm", type=int, default=3)
    ap.add_argument("--ch", type=lambda s: [int(c) for c in s.split(",")], default=None)
    ap.add_argument("--gap", type=float, default=1.5)
    ap.add_argument("--trials", action="store_true")
    a = ap.parse_args()
    out = analyze(a.csv, a.win, a.lat, a.harm, a.ch, a.gap)
    if a.trials:
        for r in out["detail"]:
            print(f"{r['key']:>4} 정답 {r['target_f']:>5}Hz → 판독 {r['pred_f']:>5}Hz  r={r['r']:.3f} {'O' if r['pred_f'] == r['target_f'] else 'X'}")
    print(f"시행 {out['trials']} · 정확도 {out['accuracy']*100:.1f}% · 표적 {out['targets']} · 창 {out['win_s']}s · ITR {out['itr_bits_min']} bits/min")
