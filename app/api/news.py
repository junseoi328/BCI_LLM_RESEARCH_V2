"""Bounded public RSS context; no user conversation is sent to the publisher."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from threading import Lock
import math
import re
import time
import xml.etree.ElementTree as ET

import httpx
from fastapi import APIRouter

router = APIRouter(tags=["speller-ui"])
# 환자 대화에서 실제로 오가는 화제 위주: 시사·사회·경제·건강·문화·연예·스포츠
FEEDS = {"시사": "politics", "사회": "society", "경제": "economy", "건강": "health",
         "문화": "culture", "연예": "entertainment", "스포츠": "sports"}
MAX_ITEMS = 600

# --- 요즘 이슈 분석: 제목에서 핵심어를 뽑아 최근일수록 무겁게 세고, 같이 나오는 말로 이슈를 묶는다.
# 원문은 저장·전송하지 않고 제목과 링크만 쓴다.
_JOSA = re.compile(r"(에서는|에게서|으로서|으로써|에서|에게|한테|으로|까지|부터|처럼|보다|이라|이나|라는|이란|"
                   r"은|는|이|가|을|를|의|에|와|과|로|께)$")   # 도·만은 뺀다: 한반도→한반, 경기도→경기가 됐다
_STOP = set("""속보 종합 단독 영상 포토 사진 그래픽 오늘 내일 어제 이번 지난 관련 위해 대해 통해 이후 발표 공개 진행 기자
연합뉴스 결과 가능 확인 정부 국내 올해 내년 전년 대비 개최 출시 위한 있는 없는 한다 했다 된다 것 등 및 또 더 수 중
1위 2위 3위 개월 이상 이하 최대 최소 전국 지역 시장 사업 추진 계획 예정 기념 행사 참석 방문 논의 협력 강화 지원 확대
선정 대상 운영 마련 제공 실시 시작 결과 의혹 입장 우려 사실 문제 상황 필요 가운데 앞두고 위해서 따라 대한 위한
억원 조원 만원 천만원 분기 상반기 하반기 한국 국가 세계 글로벌 대응 진출 목표 만에 가능성 활성화 참여 조성 통합 혁신
업무협약 협약 대표 허용 충돌 개관 초청 기부 증가 감소 상승 하락 최고 최저 역대 사상 신규 기존 공식 본격 추가 재개
서울 부산 대구 인천 광주 대전 울산 세종 경기도 강원 충북 충남 전북 전남 경북 경남 제주 수도권 지자체 시민 주민
도민 시청 군청 도청 의회 위원회 위원장 대표이사 회장 사장 장관 차관 의원 관계자 전문가 교수 연구 조사 분석 전망
강조 주장 지적 촉구 요구 제안 당부 언급 설명 공개해 이유 방안 대책 정책 제도 개선 개정 시행 적용 기준 규모 수준
함께 번째 내달 기대 효과 분야 공동 확보 점검 개발 심도 맞손 동료 체험 브랜드 설치 선수들 다양한 모든
감독 경기 리그 개막 선수 후보 코치 행정 미국 중국 일본 대화 파견 폐지 국비 수비 공격 시즌 경기도""".split())
_GENERIC_CATS = 4   # 일곱 분야 중 넷 이상에 고루 나오는 말은 화제가 아니라 상투어
_VERBISH = re.compile(r"(다|요|며|고|서|던|는데|겠|었|았|했|한|된|할|될|인|일)$")


def keywords(title: str) -> set[str]:
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)|<[^>]*>|[\"'“”‘’…·]", " ", title)
    out = set()
    for tok in re.findall(r"[가-힣]{2,10}|[A-Z]{2,6}", t):
        tok = _JOSA.sub("", tok)
        if len(tok) < 2 or tok in _STOP or (len(tok) >= 3 and _VERBISH.search(tok)):
            continue
        out.add(tok)
    return out


def analyze(items: list[dict], now: datetime, top: int = 8) -> tuple[list[dict], list[list]]:
    """(이슈 목록, 화제어 [단어, 제목 수, 점수]). 점수는 제목마다 0.5^(경과일/2) — 이틀마다 절반."""
    kws, score, df = [], {}, {}
    for it in items:
        age = max(0.0, (now - datetime.fromisoformat(it["published_at"])).total_seconds() / 86400)
        w = math.pow(0.5, age / 2)
        k = keywords(it["title"])
        kws.append((it, k, w))
        for x in k:
            score[x] = score.get(x, 0.0) + w
            df[x] = df.get(x, 0) + 1
    cats_of = {}
    for it, k, _ in kws:
        for x in k:
            cats_of.setdefault(x, set()).add(it["category"])
    ranked = sorted((x for x in score if df[x] >= 2 and len(cats_of[x]) < _GENERIC_CATS),
                    key=lambda x: (-score[x], -len(x), x))  # 동점은 긴(구체적) 말 먼저 — set 순서에 기대지 않음
    trends = [[x, df[x], round(score[x], 2)] for x in ranked[:200]]
    issues, used = [], set()
    for head in ranked:
        if len(issues) >= top:
            break
        group = [(it, k, w) for it, k, w in kws if head in k]
        urls = {it["url"] for it, _, _ in group}
        if len(group) < 2 or len(urls & used) > 0.6 * len(urls):
            continue
        co = {}
        for _, k, w in group:
            for x in k - {head}:
                co[x] = co.get(x, 0.0) + w
        words = [x for x in sorted(co, key=lambda x: (-co[x], -len(x), x)) if df.get(x, 0) >= 2 and x in score
                 and len(cats_of[x]) < _GENERIC_CATS][:3]
        cats = {}
        for it, _, w in group:
            cats[it["category"]] = cats.get(it["category"], 0.0) + w
        group.sort(key=lambda g: g[0]["published_at"], reverse=True)
        issues.append(dict(keyword=head, words=words, category=max(cats, key=cats.get), count=len(group),
                           score=round(score[head], 2),
                           titles=[dict(title=it["title"], url=it["url"], published_at=it["published_at"])
                                   for it, _, _ in group[:2]]))
        used |= urls
    return issues, trends
_lock = Lock()
_items: list[dict] = []
_checked = 0.0
_updated: str | None = None
_failed: list[str] = []


def parse_feed(body: bytes, category: str, now: datetime) -> list[dict]:
    result = []
    for item in ET.fromstring(body).findall("./channel/item")[:100]:
        title = " ".join((item.findtext("title") or "").split())[:180]
        url = item.findtext("link") or ""
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
            if published.tzinfo is None:
                continue
        except (ValueError, TypeError, OverflowError):
            continue
        if not title or not url.startswith("https://www.yna.co.kr/"):
            continue
        if now - timedelta(days=14) <= published <= now:
            result.append(dict(title=title, url=url, category=category,
                               published_at=published.isoformat(), source="연합뉴스"))
    return result


def fetch_feed(slug: str) -> bytes:
    with httpx.stream("GET", f"https://www.yna.co.kr/rss/{slug}.xml",
                      timeout=httpx.Timeout(5, connect=3), follow_redirects=False) as response:
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_bytes(65536):
            size += len(chunk)
            if size > 2_000_000:
                raise ValueError("RSS exceeds size limit")
            chunks.append(chunk)
        return b"".join(chunks)


@router.get("/speller/news")
def news():
    global _checked, _items, _updated, _failed
    now = datetime.now(timezone.utc)
    with _lock:
        # Refresh on use, at most every six hours; failed feeds retry after ten minutes.
        if not _checked or time.monotonic() - _checked >= (600 if _failed else 21600):
            merged = {item["url"]: item for item in _items}
            failed = []
            succeeded = False
            for category, slug in FEEDS.items():
                try:
                    for item in parse_feed(fetch_feed(slug), category, now):
                        merged[item["url"]] = item
                    succeeded = True
                except (httpx.HTTPError, ValueError, ET.ParseError):
                    failed.append(category)
            _items = sorted(merged.values(), key=lambda i: i["published_at"], reverse=True)[:MAX_ITEMS]
            _checked, _failed = time.monotonic(), failed
            if succeeded:
                _updated = now.isoformat()
        _items = [i for i in _items if datetime.fromisoformat(i["published_at"]) >= now - timedelta(days=14)]
        issues, trends = analyze(_items, now)
        return {"items": _items, "issues": issues, "trends": trends, "updated_at": _updated,
                "unavailable": _failed, "retention_days": 14, "refresh_hours": 6}
