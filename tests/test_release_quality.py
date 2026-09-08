from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import session as session_api
from app.errors import LLMServiceError
from app.llm.demo_resilient_client import DemoResilientLanguageModelClient
from app.llm.habitual_store import HabitualPhraseStore
from app.llm.mock_client import MockLanguageModelClient
from app.main import app
from app.pipeline.eeg import normalized_eeg_hypotheses
from app.pipeline.normalize import normalize_request
from app.pipeline.service import BCILanguagePipeline
from app.schemas import EEGHypothesis, Partner, PredictionRequest, Situation
from app.sessions.manager import InMemorySessionManager


def demo_client():
    client = DemoResilientLanguageModelClient.__new__(DemoResilientLanguageModelClient)
    client.live = MockLanguageModelClient()
    client.mock = MockLanguageModelClient()
    client.generator_model_name = 'test-generator'
    client.ranker_model_name = 'test-ranker'
    return client


def test_production_demo_forwards_fillmask():
    client = demo_client()
    client.live.generate_recovery_candidates = Mock(wraps=client.live.generate_recovery_candidates)
    response = BCILanguagePipeline(client).predict(PredictionRequest(
        bci_input='ㅁㅈ', fill_mask_reference_text='물 줘', fill_mask_target_index=1,
    ))
    assert [c.text for c in response.candidates] == ['물 좀']
    assert response.recovery_mode == 'fill_mask'
    client.live.generate_recovery_candidates.assert_called_once()
    assert client.live.generate_recovery_candidates.call_args.kwargs['target_index'] == 1


def test_demo_fallback_is_visible_and_constrained():
    client = demo_client()
    client.live.generate_recovery_candidates = Mock(side_effect=LLMServiceError('timeout', 'timeout'))
    response = BCILanguagePipeline(client).predict(PredictionRequest(
        bci_input='ㅁㅈ', fill_mask_reference_text='물 줘', fill_mask_target_index=1,
    ))
    assert response.fallback == 'demo_phrase_bank'
    assert response.candidates[0].text == '물 좀'


def test_session_keeps_manual_context_and_private_habitual(monkeypatch, tmp_path):
    monkeypatch.setattr(session_api, 'habitual_store', HabitualPhraseStore(tmp_path / 'phrases.json'))
    seen = []
    def run(request):
        seen.append(request)
        return BCILanguagePipeline(MockLanguageModelClient()).predict(request)
    monkeypatch.setattr(session_api, 'run_prediction', run)
    with TestClient(app) as api:
        ids = [api.post('/session/start', json={'partner': 'family', 'situation': 'general'}).json()['session_id'] for _ in range(2)]
        api.post(f'/session/{ids[0]}/select_text', json={'text': '내 개인 문장'})
        r = api.post(f'/session/{ids[0]}/predict', json={'bci_input': 'ㄷㅇㅈ', 'recent_context': ['목이 말라']})
        assert r.status_code == 200
        assert seen[0].recent_context == ['내 개인 문장', '목이 말라']
        assert api.get(f'/session/{ids[1]}/habitual').json()['phrases'] == []


def test_sessions_expire_and_evict_least_recently_used():
    now = [0.0]
    manager = InMemorySessionManager(max_sessions=2, ttl_seconds=10, clock=lambda: now[0])
    first = manager.start(Partner.family, Situation.general)
    second = manager.start(Partner.family, Situation.general)
    manager.get(first.session_id)
    third = manager.start(Partner.family, Situation.general)
    assert manager.get(second.session_id) is None
    assert manager.get(first.session_id)
    now[0] = 11
    assert manager.get(third.session_id) is None
    assert manager.get(first.session_id) is None


@pytest.mark.parametrize('score', [float('inf'), float('-inf'), float('nan')])
def test_nonfinite_eeg_scores_are_rejected(score):
    with pytest.raises(ValueError):
        EEGHypothesis(initials='ㄱ', score=score)


def test_eeg_top_hypothesis_is_not_lost_by_input_order():
    request = PredictionRequest(bci_input='ㄱ', eeg_hypotheses=[
        EEGHypothesis(initials='ㄱ', score=.1) for _ in range(5)
    ] + [EEGHypothesis(initials='ㄴ', score=.9)])
    assert normalized_eeg_hypotheses(request)[0][0] == 'ㄴ'


@pytest.mark.parametrize('extra', [
    {'fill_mask_reference_text': '밥 줘', 'fill_mask_target_index': 1},
    {'spelled_syllables': {8: '물'}},
])
def test_invalid_recovery_does_not_silently_change_intent(extra):
    with pytest.raises(HTTPException):
        normalize_request(PredictionRequest(bci_input='ㅁㅈ', **extra))
