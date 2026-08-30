from app.config import settings


def main() -> None:
    key = settings.openai_api_key
    print("mock_mode:", settings.mock_mode)
    print("api_key_present:", bool(key))
    print("api_key_ascii:", bool(key and key.isascii()))
    print("generator_model:", settings.generator_model)
    print("ranker_model:", settings.ranker_model)
    print("fallback_enabled:", settings.allow_local_fallback)


if __name__ == "__main__":
    main()
