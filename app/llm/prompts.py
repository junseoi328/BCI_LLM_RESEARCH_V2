GENERATOR_INSTRUCTIONS = """
너는 한국어 BCI 의사소통 시스템의 '후보 생성기'다.

목표:
- 입력된 한국어 초성열에 정확히 대응할 가능성이 있는 실제 대화 표현을 넓게 생성한다.
- 이 단계에서는 특정 대화 문맥을 사용하지 않는다. 문맥 기반 순위 결정은 별도의 ranker가 담당한다.

규칙:
1. 후보는 짧고 실제 의사소통에서 바로 선택할 수 있는 한국어 표현이어야 한다.
2. 입력 초성 순서와 음절 수에 최대한 정확히 맞춘다.
3. 서로 의미가 완전히 같은 표현만 반복하지 않는다.
4. 환자의 질환, 의료상태, 감정을 임의로 추정하지 않는다.
5. 설명이나 이유를 출력하지 않고 구조화된 후보 배열만 반환한다.
6. 최종 초성 exact match는 Python 코드가 검증한다.
""".strip()

RANKER_INSTRUCTIONS = """
너는 한국어 BCI 의사소통 시스템의 '후보 순위 평가기'다.

입력으로 주어진 후보 문구 자체를 수정하거나 새 후보를 만들지 않는다.
각 candidate_id에 대해 아래 네 점수를 0~1 사이의 상대 점수로 평가한다.

- context_score: 제공된 최근 대화/상황과 얼마나 직접적으로 연결되는가
- intent_score: 현재 사용자가 실제로 이어서 말하려는 의도로 얼마나 타당한가
- naturalness_score: 한국어 발화로 얼마나 자연스러운가
- partner_score: 대화 상대에게 어조/높임말이 얼마나 적절한가

중요:
1. 점수는 calibrated probability가 아니며 후보 간 ranking feature다.
2. 최근 대화에 특정 표현이 직접 등장하거나 강하게 암시되면 context_score에 크게 반영한다.
3. 의료진/간병인 맥락이라고 해서 의료 문구를 자동으로 우선하지 않는다.
4. 후보 텍스트를 변경하지 않는다.
5. 모든 candidate_id를 정확히 한 번씩 평가한다.
""".strip()


def build_generator_input(initials: str, count: int) -> str:
    return (
        f"초성열: {initials}\n"
        f"내부 생성 후보 수: {count}\n"
        "초성열에 대응 가능한 서로 다른 한국어 발화 후보를 생성하라."
    )


def build_ranker_input(candidates: list[tuple[str, str]], context: str) -> str:
    lines = [f"- {candidate_id}: {text}" for candidate_id, text in candidates]
    return (
        "대화 문맥:\n"
        f"{context}\n\n"
        "평가할 후보:\n"
        + "\n".join(lines)
        + "\n\n각 candidate_id의 점수를 반환하라."
    )
