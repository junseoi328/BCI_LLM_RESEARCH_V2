import hashlib
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

router = APIRouter(tags=["speller-ui"])
HTML_PATH = Path(__file__).resolve().parents[1] / "static" / "bci_speller.html"


@lru_cache(maxsize=4)
def _load(path: str, mtime_ns: int) -> tuple[bytes, str]:
    # mtime 이 키에 들어 있어 개발 중 파일을 고치면 재시작 없이 새로 읽는다.
    body = Path(path).read_bytes()
    return body, '"' + hashlib.sha256(body).hexdigest()[:16] + '"'


def _page(request: Request, path: Path) -> Response:
    """640KB 페이지를 요청마다 디스크에서 읽어 다시 보내지 않는다.

    no-cache 는 "매번 서버에 확인하라"는 뜻이라 배포 즉시 새 버전이 보이는 건 그대로다.
    달라진 게 없으면 본문 없이 304 로 답한다.
    """
    body, etag = _load(str(path), path.stat().st_mtime_ns)
    headers = {"Cache-Control": "no-cache", "ETag": etag}
    # 앞단 프록시가 압축하면서 W/ 를 붙이거나 여러 값을 보낼 수 있어 포함 여부로 본다.
    if etag in request.headers.get("if-none-match", ""):
        return Response(status_code=304, headers=headers)
    return Response(body, media_type="text/html; charset=utf-8", headers=headers)


@router.get("/speller", response_class=HTMLResponse)
def bci_speller(request: Request):
    return _page(request, HTML_PATH)


@router.get("/speller/research", response_class=HTMLResponse)
def research_speller(request: Request):
    return _page(request, HTML_PATH.with_name("research_speller.html"))


# iPhone '홈 화면에 추가' 로 열면 주소창 없이 앱처럼 뜬다.
MANIFEST = {
    "name": "이심전심 BCI Speller",
    "short_name": "이심전심",
    "start_url": "/speller",
    "scope": "/speller",
    "display": "standalone",
    "background_color": "#07080d",
    "theme_color": "#07080d",
    "lang": "ko",
    "icons": [{"src": "/speller/icon.png", "sizes": "512x512", "type": "image/png", "purpose": "any"}],
}


@router.get("/speller/manifest.webmanifest", include_in_schema=False)
def manifest():
    return JSONResponse(MANIFEST, media_type="application/manifest+json")


@router.get("/speller/icon.png", include_in_schema=False)
def icon():
    return FileResponse(HTML_PATH.with_name("icon.png"), media_type="image/png",
                        headers={"Cache-Control": "public, max-age=604800"})
