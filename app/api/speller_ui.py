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


def _page(request: Request, path: Path, media_type: str = "text/html; charset=utf-8") -> Response:
    """640KB 페이지를 요청마다 디스크에서 읽어 다시 보내지 않는다.

    no-cache 는 "매번 서버에 확인하라"는 뜻이라 배포 즉시 새 버전이 보이는 건 그대로다.
    달라진 게 없으면 본문 없이 304 로 답한다.
    """
    body, etag = _load(str(path), path.stat().st_mtime_ns)
    headers = {"Cache-Control": "no-cache", "ETag": etag}
    # 앞단 프록시가 압축하면서 W/ 를 붙이거나 여러 값을 보낼 수 있어 포함 여부로 본다.
    if etag in request.headers.get("if-none-match", ""):
        return Response(status_code=304, headers=headers)
    return Response(body, media_type=media_type, headers=headers)


DICT_PATH = HTML_PATH.with_name("dict.txt")


@lru_cache(maxsize=4)
def _speller(html_mtime: int, dict_mtime: int) -> tuple[bytes, str, str]:
    """페이지 안의 __DICT_V__ 를 사전 파일 해시로 바꿔 둔다. 사전 주소가 내용마다 달라지므로
    브라우저가 사전을 1년 동안 캐시해도 배포하면 바로 새 것을 받는다."""
    _, dict_etag = _load(str(DICT_PATH), dict_mtime)
    html, _ = _load(str(HTML_PATH), html_mtime)
    body = html.replace(b"__DICT_V__", dict_etag.strip('"').encode())
    return body, '"' + hashlib.sha256(body).hexdigest()[:16] + '"', dict_etag


@router.get("/speller", response_class=HTMLResponse)
def bci_speller(request: Request):
    body, etag, _ = _speller(HTML_PATH.stat().st_mtime_ns, DICT_PATH.stat().st_mtime_ns)
    headers = {"Cache-Control": "no-cache", "ETag": etag}
    if etag in request.headers.get("if-none-match", ""):
        return Response(status_code=304, headers=headers)
    return Response(body, media_type="text/html; charset=utf-8", headers=headers)


@router.get("/speller/dict.txt", include_in_schema=False)
def speller_dict(request: Request, v: str = ""):
    # 약 40만 단어 + 다음 단어 표. 페이지가 붙여 준 v 가 지금 파일 해시와 같으면 내용이 바뀔
    # 일이 없으므로 1년 캐시(immutable). 다르거나 없으면 ETag 재검증.
    r = _page(request, DICT_PATH, "text/plain; charset=utf-8")
    if v and f'"{v}"' == r.headers.get("etag"):
        r.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return r


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
    "background_color": "#0C0D11",
    "theme_color": "#0C0D11",
    "lang": "ko",
    "description": "초성만으로 문장을 만드는 BCI·AAC 의사소통 스펠러",
    "icons": [{"src": "/speller/icon.png", "sizes": "512x512", "type": "image/png", "purpose": "any"}],
}


@router.get("/speller/manifest.webmanifest", include_in_schema=False)
def manifest():
    return JSONResponse(MANIFEST, media_type="application/manifest+json")


@router.get("/speller/icon.png", include_in_schema=False)
def icon():
    return FileResponse(HTML_PATH.with_name("icon.png"), media_type="image/png",
                        headers={"Cache-Control": "public, max-age=604800"})


@router.get("/speller/sw.js", include_in_schema=False)
def service_worker(request: Request):
    # 파일은 /speller/ 아래에 있지만 페이지 주소 /speller 자체도 맡아야 해서 범위를 넓혀 준다.
    r = _page(request, HTML_PATH.with_name("sw.js"), "text/javascript; charset=utf-8")
    r.headers["Service-Worker-Allowed"] = "/speller"
    return r
