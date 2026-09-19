from unittest.mock import Mock

import pytest

from app.llm.mock_client import MockLanguageModelClient
from app.llm.types import GenerationCallResult, TokenUsage
from app.pipeline.service import BCILanguagePipeline
from app.schemas import PredictionRequest


def test_fast_word_mode_filters_phrases_and_skips_cloud_ranker(monkeypatch):
    monkeypatch.setenv('ENSEMBLE_MODE', 'always')
    client = MockLanguageModelClient()
    client.generate_candidates_with_context = Mock(return_value=GenerationCallResult(
        candidates=['물 줘', '문제'], usage=TokenUsage()))
    client.rank_candidates = Mock(side_effect=AssertionError('fast mode must not call ranker'))
    response = BCILanguagePipeline(client).predict(PredictionRequest(
        bci_input='ㅁㅈ', candidate_unit='word', latency_strategy='fast'))
    assert [c.text for c in response.candidates] == ['문제']
    assert client.generate_candidates_with_context.call_args.args[1] <= 7
    assert '출력 단위' in client.generate_candidates_with_context.call_args.args[2]
    client.rank_candidates.assert_not_called()


@pytest.mark.parametrize('field,value', [('candidate_unit', 'paragraph'), ('latency_strategy', 'turbo')])
def test_research_options_are_validated(field, value):
    with pytest.raises(ValueError):
        PredictionRequest(bci_input='ㄱ', **{field: value})


def test_existing_clients_keep_balanced_sentence_defaults():
    request = PredictionRequest(bci_input='ㄱ')
    assert request.latency_strategy == 'balanced'
    assert request.candidate_unit == 'sentence'
