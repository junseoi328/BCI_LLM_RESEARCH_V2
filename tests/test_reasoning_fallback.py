from types import SimpleNamespace

import pytest

from app.llm import openai_client as oc


class BadRequestError(Exception):
    pass


def make_client(effort, fail_first):
    calls = []

    def create(**kw):
        calls.append(kw["reasoning"]["effort"])
        if fail_first and len(calls) == 1:
            raise BadRequestError("Unsupported value: 'reasoning.effort' does not support 'minimal'")
        return SimpleNamespace(status="completed", output_text='{"candidates": ["물 좀 주세요"]}', usage=None)

    c = object.__new__(oc.OpenAILanguageModelClient)
    c.client = SimpleNamespace(responses=SimpleNamespace(create=create))
    c.reasoning_effort = effort
    c.generator_model_name = c.ranker_model_name = "m"
    return c, calls


def test_unsupported_effort_falls_back_to_low_once():
    c, calls = make_client("minimal", fail_first=True)
    assert c.generate_candidates("ㅁㅈㅈㅅㅇ", 3).candidates == ["물 좀 주세요"]
    c.generate_candidates("ㅁㅈ", 3)
    assert calls == ["minimal", "low", "low"]      # 한 번 실패한 뒤로는 low 를 계속 쓴다


def test_none_steps_down_to_minimal():
    c, calls = make_client("none", fail_first=True)
    c.generate_candidates("ㅁㅈ", 3)
    assert calls == ["none", "minimal"]


def test_supported_effort_is_used_as_is():
    c, calls = make_client("minimal", fail_first=False)
    c.generate_candidates("ㅁㅈ", 3)
    assert calls == ["minimal"]


def test_other_bad_requests_are_not_swallowed():
    c, _ = make_client("low", fail_first=True)
    with pytest.raises(oc.LLMServiceError):
        c.generate_candidates("ㅁㅈ", 3)
