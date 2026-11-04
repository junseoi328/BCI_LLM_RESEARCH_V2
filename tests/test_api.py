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
