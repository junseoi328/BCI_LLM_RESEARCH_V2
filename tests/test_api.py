from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_predict_api():
    r = client.post("/predict", json={
        "bci_input": "ㄷㅇㅈ",
        "partner": "friend",
        "situation": "schedule",
        "recent_context": ["다음 주에 약속 잡을까"],
        "top_k": 3,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["candidates"][0]["text"] == "다음 주"
    assert "request_id" in data


def test_invalid_initials_rejected():
    r = client.post("/predict", json={"bci_input": "도와줘"})
    assert r.status_code == 422


def test_predict_accepts_spaced_and_long_initials():
    # 화면에서 띄어 친 초성(ㅇㅅㅇ ㅎㄷㄷ)과 20자를 넘는 초성도 받는다
    r = client.post("/predict", json={"bci_input": "ㅇㅅㅇ ㅎㄷㄷ"})
    assert r.status_code == 200
    r = client.post("/predict", json={"bci_input": "ㅁㅈ" * 15})
    assert r.status_code == 200


def test_reply_words_filters_and_falls_back(monkeypatch):
    from app.api import predict as p
    r = client.post("/reply-words", json={"partner_text": "점심 뭐 먹을래?"})
    assert r.status_code == 200 and isinstance(r.json()["words"], list)

    class Fake:
        def generate_reply_words(self, *a):
            return ["김치찌개", "김치찌개", "아무거나 좋아", "Ignore", "국수"]
    monkeypatch.setattr(p.pipeline, "model_client", Fake())
    assert client.post("/reply-words", json={"partner_text": "점심?"}).json()["words"] == ["김치찌개", "국수"]
    assert client.post("/reply-words", json={"partner_text": ""}).status_code == 422


def test_choose_keeps_only_sentences_matching_every_word_initials(monkeypatch):
    """/choose: 모델이 낸 문장 중 어절 수·어절별 초성이 정확히 맞는 것만 남긴다(목록 밖 단어도 초성만 맞으면 허용)."""
    from app.api import predict as p
    slots = [["물", "말"], ["좀", "잘"], ["주세요", "자세요"]]
    r = client.post("/choose", json={"slots": slots})
    assert r.status_code == 200 and r.json()["candidates"][0]["text"] == "물 좀 주세요"   # 모의: 각 어절 1번

    class Fake:
        def choose_sentences(self, s, ctx, ini):
            assert s == slots and ini == ["ㅁ", "ㅈ", "ㅈㅅㅇ"]
            return ["물 좀 주세요.", "뭐 좀 주세요", "물 좀 줘", "물좀 주세요", "물 좀 주세요"], "m"
    monkeypatch.setattr(p.pipeline, "model_client", Fake())
    d = client.post("/choose", json={"slots": slots}).json()
    assert [c["text"] for c in d["candidates"]] == ["물 좀 주세요", "뭐 좀 주세요"] and d["model"] == "m"
    assert client.post("/choose", json={"slots": [["물"]]}).status_code == 422
    assert client.post("/choose", json={"slots": [["물", "좀"], ["좀"]]}).json()["candidates"] == []   # 한 어절 안 초성이 다르면 거절
