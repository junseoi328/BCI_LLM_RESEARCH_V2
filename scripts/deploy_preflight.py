from __future__ import annotations

import os
import sys


def main() -> int:
    required_modules = [
        "fastapi",
        "uvicorn",
        "openai",
        "pydantic",
    ]
    for module in required_modules:
        try:
            __import__(module)
        except Exception as exc:
            print(f"[FAIL] import {module}: {exc}")
            return 2

    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        print("[WARN] OPENAI_API_KEY is not set. Live/demo mode will fail.")
    else:
        print("[OK] OPENAI_API_KEY is set (value hidden).")

    try:
        from app.main import app
    except Exception as exc:
        print(f"[FAIL] import app.main: {type(exc).__name__}: {exc}")
        return 3

    paths = sorted({getattr(route, "path", "") for route in app.routes})
    print("[ROUTES]", ", ".join(paths))

    for needed in ["/health", "/predict", "/speller"]:
        if needed not in paths:
            print(f"[WARN] missing expected route: {needed}")

    print("[OK] preflight complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
