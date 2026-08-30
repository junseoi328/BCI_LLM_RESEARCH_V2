from app.config import settings
from app.llm.mock_client import MockLanguageModelClient
from app.llm.openai_client import OpenAILanguageModelClient
from app.llm.types import LanguageModelClient


def get_language_model_client() -> LanguageModelClient:
    if settings.mock_mode:
        return MockLanguageModelClient()
    return OpenAILanguageModelClient()
