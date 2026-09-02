from __future__ import annotations

from pathlib import Path
import shutil

SERVICE = Path("app/pipeline/service.py")
BACKUP = Path("app/pipeline/service.py.before_v7_v2")

OLD = "from app.llm.factory import get_language_model_client"
NEW = (
    "from app.llm.factory_v7_v2 import "
    "get_language_model_client_v7 as get_language_model_client"
)


def main() -> None:
    text = SERVICE.read_text(encoding="utf-8")
    if NEW in text:
        print("v7_v2 factory already installed")
        return
    if OLD not in text:
        raise SystemExit("service.py에서 기존 factory import를 찾지 못했습니다.")
    if not BACKUP.exists():
        shutil.copy2(SERVICE, BACKUP)
    SERVICE.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("INSTALLED v7_v2 factory")
    print("Backup:", BACKUP)


if __name__ == "__main__":
    main()
