from pathlib import Path
import shutil
S=Path("app/pipeline/service.py")
OLD="from app.llm.factory import get_language_model_client"
NEW="from app.llm.factory_final import get_language_model_client_final as get_language_model_client"
def main():
    t=S.read_text(encoding="utf-8")
    if NEW not in t:
        if OLD not in t: raise RuntimeError("기본 factory import를 찾지 못함. experimental factory를 먼저 원복하세요.")
        b=Path("app/pipeline/service.py.before_final_local")
        if not b.exists(): shutil.copy2(S,b)
        S.write_text(t.replace(OLD,NEW,1),encoding="utf-8")
    print("service.py patched")
    print("app/main.py에 추가:")
    print("from app.api.model_lab import router as model_lab_router")
    print("app.include_router(model_lab_router)")
if __name__=="__main__": main()
