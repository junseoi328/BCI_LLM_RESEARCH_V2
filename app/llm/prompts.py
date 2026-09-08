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

# ---------------------------------------------------------------------------
# Recovery prompts (SpeakFaster KeywordAE / FillMask; Cai et al. 2024,
# Nature Communications, "Using large language models to accelerate
# communication for eye gaze typing users with ALS"). These only fire when
# the initials-only Top-K failed to contain the intended phrase, so they run
# far less often than the base generator/ranker and can afford to spend more
# effort per call for much higher hit-rate.
# ---------------------------------------------------------------------------

RECOVERY_KEYWORD_INSTRUCTIONS = """
너는 한국어 BCI 의사소통 시스템의 'KeywordAE 복구 생성기'다.
사용자는 처음에 초성열만으로 입력했지만 원하는 표현이 Top 후보에 없어서,
Auto Toggle 자모 키보드로 특정 음절 위치의 정확한 글자를 직접 완성해 밝혔다.
(SpeakFaster 논문의 KeywordAE를 한국어 음절 단위에 적용하며, 사용자가 abbreviation의
일부를 직접 spelling out 한 상황이다.)

규칙:
1. 입력에 명시된 '고정 음절'은 절대 다른 글자로 바꾸지 않고 정확히 그 글자를 해당 위치에 사용한다.
2. 고정되지 않은 나머지 위치는 주어진 초성열에 정확히 대응해야 한다.
3. 문맥에 맞는 실제 대화 표현만 생성한다.
4. 서로 다른 표현을 넓게 생성한다 (같은 표현 반복 금지).
5. 설명 없이 구조화된 후보 배열만 반환한다.
6. 최종 검증(초성 exact match + 고정 음절 일치)은 Python 코드가 담당한다.
""".strip()

RECOVERY_FILLMASK_INSTRUCTIONS = """
너는 한국어 BCI 의사소통 시스템의 'FillMask 복구 생성기'다.
사용자가 선택하려던 문구는 거의 맞지만 정확히 한 음절 위치만
틀렸다고 판단해서, 그 위치만 바꾼 대안들을 요청했다.
(SpeakFaster의 단어 단위 FillMask를 한국어 음절 단위에 적용한 복구 방식이다.)

규칙:
1. '기준 문장'에서 지정된 위치를 제외한 모든 음절/글자는 절대 바꾸지 않는다.
2. 지정된 위치의 한 음절만 자연스러운 다른 음절로 교체한 서로 다른 후보를 여러 개 만든다.
3. 교체하는 위치도 주어진 전체 초성열의 해당 위치 초성과 정확히 일치해야 한다.
4. 문맥에 맞고 실제로 쓰일 법한 표현만 생성한다.
5. 설명 없이 구조화된 후보 배열만 반환한다.
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


def build_keyword_ae_input(initials: str, spelled: dict[int, str], count: int, context: str) -> str:
    fixed_desc = ", ".join(f"{i + 1}번째 글자='{ch}'" for i, ch in sorted(spelled.items()))
    return (
        f"전체 초성열: {initials}\n"
        f"고정 음절(사용자가 직접 입력함): {fixed_desc}\n"
        f"생성 후보 수: {count}\n"
        f"대화 문맥:\n{context}\n\n"
        "위 고정 음절을 반드시 그대로 포함하고, 나머지 위치는 전체 초성열에 맞는 "
        "서로 다른 실제 대화 표현 후보를 생성하라."
    )


def build_fill_mask_input(initials: str, reference_text: str, target_index: int, count: int, context: str) -> str:
    return (
        f"전체 초성열: {initials}\n"
        f"기준 문장(거의 맞지만 한 곳이 틀림): {reference_text}\n"
        f"바꿔야 할 위치(0-indexed, 공백 제외 음절 기준): {target_index}\n"
        f"대안 후보 수: {count}\n"
        f"대화 문맥:\n{context}\n\n"
        "기준 문장에서 지정된 위치의 글자/단어만 바꾼 대안들을 생성하라. "
        "그 외 위치는 기준 문장과 절대 다르게 만들지 않는다."
    )
