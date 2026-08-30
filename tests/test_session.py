from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_session_flow():
    start = client.post("/session/start", json={"partner":"friend", "situation":"schedule"})
    assert start.status_code == 200
    sid = start.json()["session_id"]

    pred = client.post(f"/session/{sid}/predict", json={
        "bci_input":"ㄷㅇㅈ",
        "recent_context":["다음 주에 약속 잡을까"]
    })
    assert pred.status_code == 200
    candidate_id = pred.json()["candidates"][0]["candidate_id"]

    select = client.post(f"/session/{sid}/select", json={"candidate_id":candidate_id})
    assert select.status_code == 200
    assert select.json()["sentence"]

    undo = client.post(f"/session/{sid}/undo")
    assert undo.status_code == 200
