"""tools/ssvep_offline.py가 앱 CSV 형식(#M·#E·표본)을 읽고 CCA로 정답 주파수를 맞히는지 — 합성 SSVEP로."""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from ssvep_offline import analyze  # noqa: E402

SR = 250
TABLE = [{"i": i, "key": f"k{i}", "f": round(8 + 0.2 * i, 1), "ph": round((0.35 * math.pi * i) % (2 * math.pi), 4)} for i in range(29)]


def _write(path, amp, seed=0):
    rng = np.random.default_rng(seed)
    rows, events, t_ms = [], [], 0.0
    def add(n, sig=None):
        nonlocal t_ms
        for j in range(n):
            ch = rng.normal(0, 10, 8)
            if sig is not None:
                ch[:3] += sig[j]
            rows.append([t_ms, t_ms + 3, len(rows), *ch])
            t_ms += 1000 / SR
    add(SR)                                                 # 쉼 1초
    for k in TABLE:
        on = t_ms
        t = np.arange(int(2.2 * SR)) / SR
        lag = np.clip(t - 0.14, 0, None)                    # 시각 지연 140ms
        sig = amp * (np.sin(2 * math.pi * k["f"] * lag + k["ph"]) + 0.5 * np.sin(4 * math.pi * k["f"] * lag)) * (t >= 0.14)
        events.append({"type": "stim_on", "t": on, "target": k["i"], "key": k["key"], "f": k["f"], "ph": k["ph"]})
        add(len(t), sig)
        events.append({"type": "stim_off", "t": t_ms, "aborted": False})
        add(SR // 2)
    lines = ["#M " + json.dumps({"srate": SR, "table": TABLE})] + ["#E " + json.dumps(e) for e in events]
    lines += ["t_ms,arrival_ms,sample,ch1,ch2,ch3,ch4,ch5,ch6,ch7,ch8"] + [",".join(f"{v:.3f}" for v in r) for r in rows]
    path.write_text("\n".join(lines), encoding="utf-8")


def test_cca_finds_the_flickering_key(tmp_path):
    p = tmp_path / "ssvep.csv"
    _write(p, amp=4.0)
    out = analyze(str(p), win=2.0)
    assert out["trials"] == 29 and out["targets"] == 29
    assert out["accuracy"] >= 0.9, out["accuracy"]
    assert out["itr_bits_min"] > 50


def test_noise_alone_stays_near_chance(tmp_path):
    p = tmp_path / "noise.csv"
    _write(p, amp=0.0, seed=1)
    assert analyze(str(p), win=2.0)["accuracy"] <= 0.2
