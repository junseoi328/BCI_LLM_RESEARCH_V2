from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_speller_page_revalidates_with_etag():
    first = client.get("/speller")
    assert first.status_code == 200
    assert first.headers["content-type"].startswith("text/html")
    assert "<html" in first.text
    etag = first.headers["etag"]

    # 달라진 게 없으면 본문을 다시 보내지 않는다
    again = client.get("/speller", headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.content == b""

    # 앞단 프록시가 압축하며 약한 검증자로 바꿔 보내도 맞아야 한다
    weak = client.get("/speller", headers={"If-None-Match": "W/" + etag})
    assert weak.status_code == 304

    # 다른 버전을 들고 있으면 전체를 받는다
    stale = client.get("/speller", headers={"If-None-Match": '"old"'})
    assert stale.status_code == 200 and stale.headers["etag"] == etag


def test_research_page_is_served():
    r = client.get("/speller/research")
    assert r.status_code == 200 and "etag" in r.headers


def test_home_screen_app_files():
    m = client.get("/speller/manifest.webmanifest")
    assert m.status_code == 200 and m.json()["start_url"] == "/speller"
    icon = client.get(m.json()["icons"][0]["src"])
    assert icon.status_code == 200 and icon.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_dictionary_layer_file():
    r = client.get("/speller/dict.txt")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    lines = r.text.splitlines()
    assert len(lines) > 300_000                      # 국어사전 어휘 전부 + 구어 빈도
    assert {"사람", "괜찮아", "먹어요"} <= {l.rstrip("0123456789n") for l in lines[:200_000]}
    assert client.get("/speller/dict.txt", headers={"If-None-Match": r.headers["etag"]}).status_code == 304


def test_dictionary_url_is_versioned_and_cached_for_a_year():
    page = client.get("/speller").text
    assert "__DICT_V__" not in page
    import re
    v = re.search(r'/speller/dict\.txt\?v=([0-9a-f]{16})', page).group(1)
    r = client.get(f"/speller/dict.txt?v={v}")
    assert r.status_code == 200 and "immutable" in r.headers["cache-control"]
    # 옛 버전 주소로 오면 오래 캐시하지 않는다
    assert "immutable" not in client.get("/speller/dict.txt?v=0000000000000000").headers["cache-control"]


def test_service_worker_covers_speller_page():
    # /speller/sw.js 가 페이지 주소 /speller 까지 맡으려면 이 헤더가 있어야 한다
    r = client.get("/speller/sw.js")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/javascript")
    assert r.headers["service-worker-allowed"] == "/speller"
    assert 'serviceWorker.register("/speller/sw.js"' in client.get("/speller").text
