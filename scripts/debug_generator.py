from app.llm.factory import get_language_model_client
from app.config import settings

CASES = [
    ("ㅁㅈ", "물 줘"),
    ("ㅈㅅㅂㄲㅈ", "자세 바꿔줘"),
    ("ㅁㅁㄹ", "목 말라"),
]

client = get_language_model_client()

for initials, target in CASES:
    print("\n" + "=" * 70)
    print(f"INPUT  : {initials}")
    print(f"TARGET : {target}")

    result = client.generate_candidates(
        initials,
        settings.generation_count,
    )

    print(f"MODEL  : {settings.generator_model}")
    print(f"COUNT  : {len(result.candidates)}")
    print("-" * 70)

    found = False

    for i, candidate in enumerate(result.candidates, 1):

        # 현재 pipeline에서는 candidate가 str.
        # 나중에 객체 타입으로 바뀌어도 동작하도록 방어적으로 처리.
        if hasattr(candidate, "text"):
            text = candidate.text.strip()
        else:
            text = str(candidate).strip()

        is_target = text == target.strip()

        if is_target:
            found = True

        mark = "  <=== TARGET" if is_target else ""

        print(f"{i:02d}. {text}{mark}")

    print("-" * 70)
    print(f"TARGET GENERATED: {found}")