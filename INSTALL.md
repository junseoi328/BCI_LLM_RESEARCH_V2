# 설치
ZIP의 app 폴더를 기존 BCI_LLM_RESEARCH_V2의 app 폴더에 병합.

app/main.py 상단에:
from app.api.speller_ui import router as speller_ui_router

router 등록 부분에:
app.include_router(speller_ui_router)

실행:
python -m py_compile app\api\speller_ui.py
python -m uvicorn app.main:app --reload

브라우저:
http://127.0.0.1:8000/speller
