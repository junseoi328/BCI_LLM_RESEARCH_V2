from pathlib import Path

SERVICE = Path("app/pipeline/service.py")
OLD = "from app.llm.factory import get_language_model_client"
NEW = (
    "from app.llm.factory_v7_v2 import "
    "get_language_model_client_v7 as get_language_model_client"
)

text = SERVICE.read_text(encoding="utf-8")
if NEW in text:
    SERVICE.write_text(text.replace(NEW, OLD, 1), encoding="utf-8")
    print("RESTORED original factory")
else:
    print("v7_v2 factory is not installed")
