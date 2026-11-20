"""LSL → WebSocket 다리: OpenBCI GUI(Ganglion·Cyton) 등이 내보내는 LSL 뇌파를 이심전심 웹으로 보낸다.

  pip install pylsl websockets
  python tools/lsl_bridge.py            # type=EEG 스트림을 찾아 ws://127.0.0.1:8765 로 내보냄
  python tools/lsl_bridge.py --name obci_eeg1 --port 8765

웹(Chrome·Edge) 실험 패널 '실제 실험 · OpenBCI' → 'LSL 연결'. 이 PC 안(127.0.0.1)에서만 열린다.
메시지: 처음 {"meta": {name, srate, n}}, 이후 {"now": LSL 지금, "ts": [표본 LSL 시각…], "x": [[ch1..chN]…]}.
웹은 표본 시각을 '받은 순간 − (now − ts)'로 자기 시계에 맞춘다.
"""
import argparse
import asyncio
import json

from pylsl import StreamInlet, local_clock, resolve_byprop
import websockets


async def main(name: str, port: int) -> None:
    print("LSL 뇌파 스트림을 찾는 중… (OpenBCI GUI → Networking → LSL, Data Type: EEG, Start)")
    streams = resolve_byprop("name", name, timeout=30) if name else resolve_byprop("type", "EEG", timeout=30)
    if not streams:
        raise SystemExit("LSL 뇌파 스트림을 찾지 못했습니다.")
    inlet = StreamInlet(streams[0], max_chunklen=32)
    info = inlet.info()
    meta = {"name": info.name(), "srate": info.nominal_srate(), "n": info.channel_count()}
    print(f"찾음: {meta} → ws://127.0.0.1:{port}")
    clients: set = set()

    async def handler(ws, *_):
        clients.add(ws)
        await ws.send(json.dumps({"meta": meta}))
        try:
            await ws.wait_closed()
        finally:
            clients.discard(ws)

    async with websockets.serve(handler, "127.0.0.1", port):
        while True:
            chunk, ts = inlet.pull_chunk(timeout=0.0)
            if ts and clients:
                msg = json.dumps({"now": local_clock(), "ts": ts, "x": chunk})
                await asyncio.gather(*(c.send(msg) for c in list(clients)), return_exceptions=True)
            await asyncio.sleep(0.02)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="", help="LSL 스트림 이름(비우면 type=EEG 중 첫 번째)")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    asyncio.run(main(a.name, a.port))
