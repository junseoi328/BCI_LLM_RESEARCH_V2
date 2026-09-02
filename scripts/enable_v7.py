from __future__ import annotations

from pathlib import Path
import shutil


SERVICE = Path("app/pipeline/service.py")
BACKUP = Path("app/pipeline/service.py.before_v7")


def main() -> None:
    if not SERVICE.exists():
        raise SystemExit(f"{SERVICE} not found")

    text = SERVICE.read_text(encoding="utf-8")
    old = "from app.llm.factory import get_language_model_client"
    new = (
        "from app.llm.factory_v7 import "
        "get_language_model_client_v7 as get_language_model_client"
    )

    if new in text:
        print("v7 factory already enabled")
        return
    if old not in text:
        raise SystemExit(
            "예상 import를 찾지 못했습니다. service.py의 get_language_model_client import를 확인하세요."
        )

    if not BACKUP.exists():
        shutil.copy2(SERVICE, BACKUP)

    SERVICE.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("ENABLED v7 factory")
    print("Backup:", BACKUP)


if __name__ == "__main__":
    main()
