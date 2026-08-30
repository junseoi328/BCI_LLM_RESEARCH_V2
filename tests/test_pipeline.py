from app.llm.mock_client import MockLanguageModelClient
from app.pipeline.service import BCILanguagePipeline
from app.schemas import PredictionRequest


def pipeline():
    return BCILanguagePipeline(model_client=MockLanguageModelClient())


def test_context_changes_ranking():
    p = pipeline()
    schedule = p.predict(PredictionRequest(
        bci_input="ㄷㅇㅈ",
        partner="friend",
        situation="schedule",
        recent_context=["다음 주에 약속 잡을까"],
    ))
    assert schedule.candidates[0].text == "다음 주"

    posture = p.predict(PredictionRequest(
        bci_input="ㄷㅇㅈ",
        partner="family",
        situation="positioning",
        recent_context=["혼자 자세를 바꾸기 어렵다"],
    ))
    assert posture.candidates[0].text == "도와줘"


def test_pipeline_exact_initials():
    response = pipeline().predict(PredictionRequest(bci_input="ㄷㅇㅈ"))
    assert response.candidates
    assert all(c.matched_initials == "ㄷㅇㅈ" for c in response.candidates)


def test_eeg_hypothesis_path():
    response = pipeline().predict(PredictionRequest(
        bci_input="ㄷㅇㅈ",
        eeg_hypotheses=[
            {"initials": "ㄷㅇㅈ", "score": 0.7},
            {"initials": "ㅁㅈ", "score": 0.3},
        ],
        eeg_score_type="probability",
        recent_context=["목이 말라"],
    ))
    assert response.candidates
    assert any(c.matched_initials in {"ㄷㅇㅈ", "ㅁㅈ"} for c in response.candidates)


def test_response_has_usage_and_latency():
    response = pipeline().predict(PredictionRequest(bci_input="ㄷㅇㅈ"))
    assert response.latency.total_ms >= 0
    assert response.usage.total_tokens == 0
    assert response.generator_model == "mock-generator"
