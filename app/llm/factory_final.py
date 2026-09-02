from __future__ import annotations
import os
from app.llm.factory import get_language_model_client
from app.llm.local_final_client import LocalGeneratorCloudRankerClient
def get_language_model_client_final():
    enabled=os.getenv("LOCAL_BCI_GENERATOR_ENABLED","false").strip().lower()
    return LocalGeneratorCloudRankerClient() if enabled in {"1","true","yes","on"} else get_language_model_client()
