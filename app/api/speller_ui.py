from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["speller-ui"])
HTML_PATH = Path(__file__).resolve().parents[1] / "static" / "bci_speller.html"

@router.get("/speller", response_class=HTMLResponse)
def bci_speller():
    return HTMLResponse(HTML_PATH.read_text(encoding="utf-8"), headers={"Cache-Control": "no-cache"})
