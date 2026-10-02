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
