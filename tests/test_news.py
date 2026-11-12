from datetime import datetime, timedelta, timezone

from app.api.news import analyze, keywords


def _it(title, cat, hours=1, n=0):
    now = datetime(2026, 11, 12, tzinfo=timezone.utc)
    return dict(title=title, url=f"https://www.yna.co.kr/view/{cat}{n}{title[:3]}", category=cat,
                published_at=(now - timedelta(hours=hours)).isoformat(), source="연합뉴스")


def test_keywords_strip_particles_and_stopwords():
    k = keywords("[속보] 한화이글스가 한국시리즈에서 우승…팬들 환호(종합)")
    assert "한화이글스" in k and "한국시리즈" in k
    assert "속보" not in k and "종합" not in k


def test_issue_groups_titles_and_prefers_recent():
    now = datetime(2026, 11, 12, tzinfo=timezone.utc)
    items = [_it("한화이글스 한국시리즈 우승 김경문 감독 눈물", "스포츠", 1, 1),
             _it("한화이글스 우승 퍼레이드 대전 팬 몰려", "스포츠", 3, 2),
             _it("한화이글스 우승 기념 할인 행사", "경제", 5, 3),
             _it("독감 유행 주의보 발령 병원 북적", "건강", 2, 4),
             _it("독감 예방접종 서둘러야 병원 권고", "건강", 4, 5),
             _it("옛날 독감 기사", "건강", 24 * 12, 6)]
    issues, trends = analyze(items, now)
    heads = [i["keyword"] for i in issues]
    assert heads[0] == "한화이글스" and "우승" in issues[0]["words"]
    assert issues[0]["category"] == "스포츠" and issues[0]["count"] == 3
    assert "독감" in heads
    assert dict((w, df) for w, df, _ in trends)["독감"] == 3
