from __future__ import annotations

import json

from app.pipeline.service import BCILanguagePipeline
from app.schemas import PredictionRequest


def main() -> None:
    req = PredictionRequest(
        bci_input="ㄷㅇㅈ",
        partner="friend",
        situation="schedule",
        recent_context=["다음 주에 약속 잡을까"],
        top_k=3,
    )
    res = BCILanguagePipeline().predict(req)
    print(json.dumps(res.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
