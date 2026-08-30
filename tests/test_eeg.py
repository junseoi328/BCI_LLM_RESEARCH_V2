from app.pipeline.eeg import normalized_eeg_hypotheses
from app.schemas import PredictionRequest


def test_no_eeg_is_none_evidence():
    req = PredictionRequest(bci_input="ㄷㅇㅈ")
    assert normalized_eeg_hypotheses(req) == [("ㄷㅇㅈ", None)]


def test_probability_normalization():
    req = PredictionRequest(
        bci_input="ㄷㅇㅈ",
        eeg_score_type="probability",
        eeg_hypotheses=[
            {"initials": "ㄷㅇㅈ", "score": 0.6},
            {"initials": "ㄷㅇㅊ", "score": 0.2},
        ],
    )
    rows = normalized_eeg_hypotheses(req)
    assert rows[0][0] == "ㄷㅇㅈ"
    assert abs(sum(score for _, score in rows) - 1.0) < 1e-9
