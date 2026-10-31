"""이심전심 장면 그림(SVG) — STROKE 로그인 화면의 '코트 사진' 자리를 뇌파 선 + 원근 바닥선으로 대신한다.
python3 scene.py → scene_waves.svg(애니메이션용 인라인), scene_bg.txt(CSS data URI)"""
import math, random, urllib.parse
random.seed(11)
W, H = 1200, 800

def wave(y0, amp, freqs, n=240, spikes=()):
    pts = []
    ph = [random.uniform(0, 6.28) for _ in freqs]
    for i in range(n + 1):
        x = W * i / n
        y = y0 + sum(a * amp * math.sin(2 * math.pi * f * i / n + p) for (f, a), p in zip(freqs, ph))
        for (sx, sh) in spikes:   # 응시 순간의 짧은 반응(SSVEP·P300 느낌)
            d = (x - sx) / 14
            y -= sh * math.exp(-d * d)
        pts.append(f"{x:.0f},{y:.1f}")
    return "M" + " L".join(pts)

waves = [
    ("#6EA8FF", 0.9, 2.2, wave(470, 14, [(7, 1), (19, .5), (41, .25)], spikes=[(610, 70)])),
    ("#A48BFF", 0.65, 1.6, wave(520, 18, [(5, 1), (13, .6), (33, .3)], spikes=[(610, 40)])),
    ("#3DD6C6", 0.5, 1.4, wave(565, 12, [(9, 1), (23, .5), (47, .3)])),
]
# 원근 바닥선: 소실점에서 아래로 퍼지는 선(STROKE 코트 라인의 메아리)
vx, vy = 600, 430
floor = [f"M{vx},{vy} L{x},{H}" for x in range(-600, 1801, 200)]
floor += [f"M0,{y} L{W},{y}" for y in (600, 660, 735)]
stars = "".join(f'<circle cx="{random.uniform(0,W):.0f}" cy="{random.uniform(0,380):.0f}" r="{random.choice((0.8,1,1.3))}" fill="#fff" opacity="{random.uniform(.15,.5):.2f}"/>' for _ in range(46))

def svg(animated):
    cls = (lambda i: f' class="wv w{i}"') if animated else (lambda i: "")
    pl = ' pathLength="100"' if animated else ""
    paths = "".join(f'<path{cls(i)}{pl} d="{d}" fill="none" stroke="{c}" stroke-opacity="{o}" stroke-width="{w}" stroke-linejoin="round"/>'
                    for i, (c, o, w, d) in enumerate(waves))
    fl = "".join(f'<path d="{d}"/>' for d in floor)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice">'
            f'{stars}<g stroke="#fff" stroke-opacity=".07" stroke-width="1.2" fill="none">{fl}</g>{paths}</svg>')

open("scene_waves.svg", "w").write(svg(True))
open("scene_bg.txt", "w").write('url("data:image/svg+xml,' + urllib.parse.quote(svg(False).replace('"', "'"), safe=" ,:=/'.-") + '")')
print(len(svg(True)), len(open("scene_bg.txt").read()))
