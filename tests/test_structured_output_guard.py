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
