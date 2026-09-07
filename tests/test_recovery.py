"""KeywordAE / FillMask recovery + habitual-phrase tests.

Added alongside the "revised, more accurate/faster" pass driven by the team's
weekly UX/UI notes (가빈: KeywordAE >> FillMask) and the SpeakFaster paper
(Cai et al. 2024, Nature Communications). These run in CI under MOCK_MODE
(see tests/conftest.py), which is also the one place in the whole project
that can actually execute end-to-end against a live-shaped pipeline, since
the real local LoRA generator and the OpenAI client are not reachable from
the sandbox that authored this change.
"""

from fastapi.testclient import TestClient

from app.korean.initials import (
    extract_units,
    fill_mask_constraint_match,
    spelled_constraint_match,
)
from app.llm.habitual_store import HabitualPhraseStore
from app.llm.mock_client import MockLanguageModelClient
from app.main import app
from app.pipeline.filter import filter_candidates
from app.pipeline.service import BCILanguagePipeline
from app.schemas import GeneratedCandidate, PredictionRequest

client = TestClient(app)


def pipeline():
    return BCILanguagePipeline(model_client=MockLanguageModelClient())


# ---------------------------------------------------------------------------
# app.korean.initials: position-aligned unit helpers
# ---------------------------------------------------------------------------


def test_extract_units_aligns_with_extract_initials():
    assert extract_units("물 줘") == ["물", "줘"]
    assert extract_units("자세 바꿔줘") == ["자", "세", "바", "꿔", "줘"]


def test_spelled_constraint_match():
    assert spelled_constraint_match("물 줘", {0: "물"})
    assert spelled_constraint_match("물 좀", {0: "물"})
    assert not spelled_constraint_match("맥주", {0: "물"})
    assert not spelled_constraint_match("물 줘", {5: "x"})
    assert spelled_constraint_match("아무거나", None)


def test_fill_mask_constraint_match():
    assert fill_mask_constraint_match("물 좀", "물 줘", 1)
    assert not fill_mask_constraint_match("맥주", "물 줘", 1)
    assert not fill_mask_constraint_match("물 줘", "물 줘", 1)  # identical is not an alternative
    assert not fill_mask_constraint_match("물 줘줘", "물 줘", 1)  # length mismatch


# ---------------------------------------------------------------------------
# app.pipeline.filter: spelled-constraint filtering
# ---------------------------------------------------------------------------


def test_filter_candidates_with_spelled_constraint():
    candidates = [
        GeneratedCandidate(candidate_id="c1", text="물 줘", source_initials="ㅁㅈ", generation_order=1),
        GeneratedCandidate(candidate_id="c2", text="물 좀", source_initials="ㅁㅈ", generation_order=2),
        GeneratedCandidate(candidate_id="c3", text="맥주", source_initials="ㅁㅈ", generation_order=3),
    ]
    assert len(filter_candidates(candidates, "ㅁㅈ")) == 3
    kept = filter_candidates(candidates, "ㅁㅈ", spelled={0: "물"})
    assert [c.text for c in kept] == ["물 줘", "물 좀"]


# ---------------------------------------------------------------------------
# app.schemas.PredictionRequest: recovery field validation
# ---------------------------------------------------------------------------


def test_spelled_syllables_accepts_json_string_keys():
    # FastAPI/pydantic receives JSON object keys as strings; dict[int, str]
    # must coerce them, since the frontend always sends {"0": "물"} shaped JSON.
    req = PredictionRequest(bci_input="ㅁㅈ", spelled_syllables={"0": "물"})
    assert req.spelled_syllables == {0: "물"}


def test_fill_mask_fields_must_be_paired():
    import pytest

    with pytest.raises(Exception):
        PredictionRequest(bci_input="ㅁㅈ", fill_mask_reference_text="물 줘")
    with pytest.raises(Exception):
        PredictionRequest(bci_input="ㅁㅈ", fill_mask_target_index=1)
    # paired is fine
    PredictionRequest(bci_input="ㅁㅈ", fill_mask_reference_text="물 줘", fill_mask_target_index=1)


# ---------------------------------------------------------------------------
# app.pipeline.service.BCILanguagePipeline: recovery_mode end-to-end (mock)
# ---------------------------------------------------------------------------


def test_keyword_ae_recovery_pins_spelled_position():
    response = pipeline().predict(PredictionRequest(
        bci_input="ㅁㅈ",
        spelled_syllables={0: "물"},
    ))
    assert response.recovery_mode == "keyword_ae"
    assert response.candidates
    for c in response.candidates:
        assert extract_units(c.text)[0] == "물"


def test_fill_mask_recovery_varies_only_target_index():
    response = pipeline().predict(PredictionRequest(
        bci_input="ㅁㅈ",
        fill_mask_reference_text="물 줘",
        fill_mask_target_index=1,
    ))
    assert response.recovery_mode == "fill_mask"
    for c in response.candidates:
        assert fill_mask_constraint_match(c.text, "물 줘", 1)


def test_no_recovery_fields_means_recovery_mode_none():
    response = pipeline().predict(PredictionRequest(bci_input="ㄷㅇㅈ"))
    assert response.recovery_mode == "none"


# ---------------------------------------------------------------------------
# HTTP-level: /predict with recovery fields, and the new session endpoints
# ---------------------------------------------------------------------------


def test_predict_api_keyword_ae():
    r = client.post("/predict", json={
        "bci_input": "ㅁㅈ",
        "spelled_syllables": {"0": "물"},
    })
    assert r.status_code == 200
    data = r.json()
    assert data["recovery_mode"] == "keyword_ae"
    assert all(c["text"].startswith("물") for c in data["candidates"])


def test_predict_api_fill_mask_requires_both_fields():
    r = client.post("/predict", json={
        "bci_input": "ㅁㅈ",
        "fill_mask_reference_text": "물 줘",
    })
    assert r.status_code == 422


def test_session_habitual_and_select_text_flow():
    start = client.post("/session/start", json={"partner": "family", "situation": "meal"})
    sid = start.json()["session_id"]

    empty = client.get(f"/session/{sid}/habitual")
    assert empty.status_code == 200
    assert isinstance(empty.json()["phrases"], list)

    committed = client.post(f"/session/{sid}/select_text", json={"text": "물 줘"})
    assert committed.status_code == 200
    assert committed.json()["sentence"] == "물 줘"
    assert committed.json()["history"] == ["물 줘"]

    after = client.get(f"/session/{sid}/habitual")
    assert after.status_code == 200
    texts = [p["text"] for p in after.json()["phrases"]]
    assert "물 줘" in texts


# ---------------------------------------------------------------------------
# app.llm.habitual_store: tiered fallback
# ---------------------------------------------------------------------------


def test_habitual_store_tiered_fallback(tmp_path):
    store = HabitualPhraseStore(tmp_path / "habitual.json")
    store.record("family", "meal", "물 줘")
    store.record("family", "meal", "물 줘")
    store.record("family", "general", "고마워")

    exact = store.top_tiered(partner="family", situation="meal", limit=5)
    assert exact[0] == ("물 줘", 2)

    # no data for (family, positioning) -> falls back to partner-wide, still finds 고마워
    fallback = store.top_tiered(partner="family", situation="positioning", limit=5)
    assert "고마워" in [t for t, _ in fallback]
