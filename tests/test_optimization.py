from unittest.mock import Mock
from types import SimpleNamespace

import pytest

from app.llm.local_final_client import LocalGeneratorCloudRankerClient
from app.pipeline.diversity import remove_near_duplicates, text_similarity
from app.schemas import GeneratedCandidate


@pytest.mark.parametrize("threshold", [0.0, 0.5, 0.88, 1.0])
def test_diversity_preserves_reference_results(monkeypatch, threshold):
    monkeypatch.setattr(
        "app.pipeline.diversity.settings",
        SimpleNamespace(diversity_similarity_threshold=threshold),
    )
    texts = ["도와줘", "도와 줘!", "다음 주", "다음 주에", "물 주세요", "!!!", "___"]
    candidates = [
        GeneratedCandidate(candidate_id=str(i), text=text, source_initials="", generation_order=i + 1)
        for i, text in enumerate(texts)
    ]
    expected = []
    for candidate in candidates:
        if not any(text_similarity(candidate.text, old.text) >= threshold for old in expected):
            expected.append(candidate)
    assert remove_near_duplicates(candidates) == expected


def hybrid(memory, generated):
    client = LocalGeneratorCloudRankerClient.__new__(LocalGeneratorCloudRankerClient)
    client.memory = Mock()
    client.memory.candidates.return_value = memory
    client.memory_limit = 6
    client.local_generator = Mock()
    client.local_generator.generate.return_value = generated
    return client


def test_memory_filled_request_skips_inference():
    client = hybrid(["도와줘", "다음 주"], ["다음 주"])
    result = client.generate_candidates("ㄷㅇㅈ", 2)
    assert result.candidates == ["도와줘", "다음 주"]
    client.local_generator.generate.assert_not_called()


def test_invalid_and_duplicate_memory_still_runs_inference():
    client = hybrid(["도와줘", "도와줘", "물 주세요"], ["도와줘", "다음 주"])
    assert client.generate_candidates("ㄷㅇㅈ", 2).candidates == ["도와줘", "다음 주"]
    client.local_generator.generate.assert_called_once_with(initials="ㄷㅇㅈ", count=2)


def test_local_failure_preserves_memory():
    client = hybrid(["도와줘"], [])
    client.local_generator.generate.side_effect = RuntimeError("driver unavailable")
    assert client.generate_candidates("ㄷㅇㅈ", 2).candidates == ["도와줘"]


@pytest.mark.parametrize("count", [0, -1])
def test_empty_request_skips_generation(count):
    client = hybrid(["도와줘"], [])
    assert client.generate_candidates("ㄷㅇㅈ", count).candidates == []
    client.memory.candidates.assert_not_called()
    client.local_generator.generate.assert_not_called()
