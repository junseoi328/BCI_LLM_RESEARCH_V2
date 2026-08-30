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
