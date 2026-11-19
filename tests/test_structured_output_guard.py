from types import SimpleNamespace
import pytest

from app.errors import LLMServiceError
from app.llm.openai_client import _parse_structured_json_response


def test_parse_completed_structured_json():
    response = SimpleNamespace(status="completed", incomplete_details=None, output_text='{"candidates":["도와줘"]}')
    assert _parse_structured_json_response(response, "generator") == {"candidates": ["도와줘"]}


def test_incomplete_max_output_tokens_becomes_clean_error():
    response = SimpleNamespace(
        status="incomplete",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        output_text='{"candidates":["도와',
    )
    with pytest.raises(LLMServiceError) as exc_info:
        _parse_structured_json_response(response, "generator")
    assert exc_info.value.code == "incomplete_max_output_tokens"


def test_malformed_json_becomes_clean_error():
    response = SimpleNamespace(status="completed", incomplete_details=None, output_text='{"candidates":["도와')
    with pytest.raises(LLMServiceError) as exc_info:
        _parse_structured_json_response(response, "generator")
    assert exc_info.value.code == "malformed_structured_output"


def test_generator_decodes_the_spaced_initials_and_prefers_matching_words():
    """띄어 친 초성은 그대로 프롬프트에 들어가고, 어절 모양이 맞는 후보가 앞선다(align 객체 형식도 읽는다)."""
    from types import SimpleNamespace as NS
    from app.llm.openai_client import OpenAILanguageModelClient, spacing_matches
    assert spacing_matches("물 좀 주세요", "ㅁ ㅈ ㅈㅅㅇ") and not spacing_matches("뭐 좀 줘 싫어", "ㅁ ㅈ ㅈㅅㅇ")
    seen = {}
    client = OpenAILanguageModelClient.__new__(OpenAILanguageModelClient)
    client.generator_model_name = "m"
    client._usage = lambda r: None
    def fake(**kw):
        seen["input"] = kw["input"]
        return NS(status="completed", incomplete_details=None,
                  output_text='{"candidates":[{"align":"","text":"뭐좀 줘 싫어"},{"align":"ㅁ:물 ㅈ:좀 ㅈ:주 ㅅ:세 ㅇ:요","text":"물 좀 주세요"}]}')
    client._create = fake
    client._with_retry = lambda f: f()
    ctx = "사용자가 띄어 친 초성: ㅁ ㅈ ㅈㅅㅇ (공백 자리에서 어절이 나뉜다. 후보도 그 자리에서 띄어 쓴다)"
    r = client.generate_candidates("ㅁㅈㅈㅅㅇ", 3, context=ctx)
    assert "초성열: ㅁ ㅈ ㅈㅅㅇ" in seen["input"]
    assert r.candidates[0] == "물 좀 주세요"
