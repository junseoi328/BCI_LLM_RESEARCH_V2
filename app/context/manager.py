from __future__ import annotations

from app.schemas import ContextLevel, PredictionRequest


PARTNER_STYLE = {
    "family": "가족과의 자연스럽고 짧은 일상 대화. 반말/존댓말은 현재 문맥을 따른다.",
    "friend": "친구와의 자연스러운 일상 대화. 지나치게 격식적이지 않게 한다.",
    "caregiver": "간병인에게 전달하는 명확하고 짧은 요청을 우선한다.",
    "medical_staff": "의료진에게 전달하는 명확하고 정중한 표현을 우선하되, 진단을 새로 추론하지 않는다.",
    "other": "일반적인 자연스러운 한국어 대화.",
}

SITUATION_HINT = {
    "general": "일반 대화",
    "home": "집/일상 환경",
    "hospital": "병원 환경",
    "meal": "식사 또는 음료",
    "pain": "통증/불편 의사표현",
    "positioning": "자세 또는 위치 조정",
    "schedule": "일정/약속",
    "entertainment": "TV/음악/여가",
    "emergency": "긴급 도움 요청",
}


def build_context(request: PredictionRequest) -> str:
    level = request.context_level
    if level == ContextLevel.none:
        return "문맥 제공 안 함. 후보의 일반적 자연스러움만 평가한다."

    parts = [
        f"대화 상대: {request.partner.value}",
        f"상대 스타일: {PARTNER_STYLE[request.partner.value]}",
    ]
    if level in {ContextLevel.partner_situation, ContextLevel.full}:
        parts.append(f"상황: {request.situation.value} ({SITUATION_HINT[request.situation.value]})")
    if level == ContextLevel.full:
        parts.append(f"현재 작성 중 문장: {request.current_sentence or '없음'}")
        recent = " | ".join(request.recent_context[-5:]) if request.recent_context else "없음"
        parts.append(f"최근 대화: {recent}")
    return "\n".join(parts)
