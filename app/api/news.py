"""Bounded public RSS context; no user conversation is sent to the publisher."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from threading import Lock
import time
import xml.etree.ElementTree as ET

import requests
from fastapi import APIRouter

router = APIRouter(tags=["speller-ui"])
FEEDS = {"시사": "politics", "연예": "entertainment", "스포츠": "sports"}
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
    with requests.get(f"https://www.yna.co.kr/rss/{slug}.xml", timeout=(3, 5),
                      stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
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
                except (requests.RequestException, ValueError, ET.ParseError):
                    failed.append(category)
            _items = sorted(merged.values(), key=lambda i: i["published_at"], reverse=True)[:300]
            _checked, _failed = time.monotonic(), failed
            if succeeded:
                _updated = now.isoformat()
        _items = [i for i in _items if datetime.fromisoformat(i["published_at"]) >= now - timedelta(days=14)]
        return {"items": _items, "updated_at": _updated, "unavailable": _failed,
                "retention_days": 14, "refresh_hours": 6}
