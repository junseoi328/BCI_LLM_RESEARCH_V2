from app.llm.factory import get_language_model_client


def get_language_model_client_final():
    # Compatibility wrapper for branches where service.py imports factory_final.
    return get_language_model_client()
