from __future__ import annotations

from pathlib import Path


SERVICE = Path("app/pipeline/service.py")


def main() -> None:
    text = SERVICE.read_text(encoding="utf-8")
    new = (
        "from app.llm.factory_v7 import "
        "get_language_model_client_v7 as get_language_model_client"
    )
    old = "from app.llm.factory import get_language_model_client"
    if new not in text:
        print("v7 factory is not enabled")
        return
    SERVICE.write_text(text.replace(new, old, 1), encoding="utf-8")
    print("DISABLED v7 factory")


if __name__ == "__main__":
    main()
