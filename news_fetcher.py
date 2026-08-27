"""
news_fetcher.py — Lấy tin tức vĩ mô/vàng/dầu gần đây từ các nguồn RSS miễn phí.

Phase 1.5: module này CHỈ thu thập tin tức thô, không tự đánh giá sentiment
(việc đó do sentiment_analyzer.py + Groq đảm nhiệm).

Cách hoạt động:
- Đọc danh sách feed RSS từ Config.NEWS_RSS_FEEDS (mặc định vài nguồn miễn phí phổ biến
  về vàng/kinh tế vĩ mô — có thể không phải nguồn nào cũng còn hoạt động, tự kiểm tra
  và thay bằng feed khác nếu 1 nguồn nào đó lỗi liên tục).
- Lọc chỉ giữ tin trong N giờ gần nhất (NEWS_LOOKBACK_HOURS) và có chứa từ khoá liên quan
  (vàng, Fed, lãi suất, lạm phát, USD, dầu...) để tránh đưa tin không liên quan vào Groq.
- Loại trùng tiêu đề (nhiều feed có thể đăng lại cùng 1 tin).
"""

from __future__ import annotations

import calendar
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import feedparser
import requests

from config import Config

# Nhiều server (kể cả feed hợp lệ) âm thầm trả về rỗng/lỗi cho request không có
# User-Agent giống trình duyệt thật. Ngoài ra, để feedparser tự mở kết nối HTTPS
# (qua urllib bên trong nó) đôi khi gặp lỗi TLS/certificate trên Windows mà không
# ném exception rõ ràng — chỉ đánh dấu bozo=True và trả về 0 mục. Dùng `requests`
# để tự tải nội dung trước (xử lý TLS ổn định hơn nhiều), rồi mới đưa cho
# feedparser phân tích — đây là cách khắc phục phổ biến cho đúng lỗi bozo=True này.
_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
_REQUEST_TIMEOUT_SECONDS = 20
_MAX_RETRIES = 2


@dataclass
class NewsItem:
    title: str
    source: str
    published: datetime
    link: str = ""


def _parse_published(entry) -> datetime | None:
    """feedparser trả về published_parsed (time.struct_time, ĐÃ ở giờ UTC theo chuẩn RSS).

    BUG ĐÃ SỬA: bản trước dùng time.mktime(struct), nhưng mktime() diễn giải struct_time
    đầu vào là GIỜ LOCAL của máy chạy code, không phải UTC. Ở máy giờ Việt Nam (UTC+7),
    điều này làm mỗi tin bị lùi sai lệch ~7 tiếng so với UTC thật — một tin đăng lúc
    18:09 UTC thật bị tính thành 11:09 UTC, khiến tin trông "cũ" hơn thực tế 7 tiếng.
    Với NEWS_LOOKBACK_HOURS mặc định chỉ 6 giờ, gần như toàn bộ tin thật (dù vừa đăng)
    bị lọc cutoff loại bỏ oan — đây là nguyên nhân thật của triệu chứng "có mục thô
    nhưng 0 tin liên quan". calendar.timegm() diễn giải struct_time đúng là UTC, không
    áp offset timezone của máy, nên dùng nó thay cho time.mktime() ở đây.
    """
    for key in ("published_parsed", "updated_parsed"):
        struct = getattr(entry, key, None)
        if struct:
            return datetime.fromtimestamp(calendar.timegm(struct), tz=timezone.utc)
    return None


def _is_relevant(title: str) -> bool:
    title_lower = title.lower()
    return any(kw.lower() in title_lower for kw in Config.NEWS_KEYWORDS)


def fetch_recent_news(lookback_hours: int | None = None, verbose: bool = False) -> list[NewsItem]:
    """Lấy tin tức liên quan trong N giờ gần nhất từ toàn bộ feed đã cấu hình.

    Trả về danh sách đã loại trùng tiêu đề, sắp xếp mới nhất trước.
    Nếu 1 feed lỗi (mạng, feed die, bị chặn...) sẽ bỏ qua feed đó và tiếp tục với
    feed khác, không làm crash toàn bộ — vì phần này chạy nền song song với vòng
    lặp phân tích giá chính.

    verbose=True in thêm số liệu chẩn đoán (HTTP status, số mục thô lấy được từ
    mỗi feed trước khi lọc theo thời gian/từ khoá) — dùng khi cần debug "0 tin".
    """
    lookback_hours = lookback_hours or Config.NEWS_LOOKBACK_HOURS
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    seen_titles: set[str] = set()
    items: list[NewsItem] = []

    for feed_url in Config.NEWS_RSS_FEEDS:
        resp = None
        last_error = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = requests.get(feed_url, headers=_REQUEST_HEADERS, timeout=_REQUEST_TIMEOUT_SECONDS)
                resp.raise_for_status()  # ném lỗi rõ ràng nếu HTTP status là 4xx/5xx
                break
            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < _MAX_RETRIES:
                    print(f"⚠️  Lần {attempt} tải feed {feed_url} lỗi ({e}) — thử lại...")
                    time.sleep(2)
                continue

        if resp is None:
            print(f"⚠️  Lỗi tải feed {feed_url} sau {_MAX_RETRIES} lần thử: {last_error} — "
                  f"bỏ qua, tiếp tục feed khác. (Nếu lỗi lặp lại, kiểm tra mạng hoặc thử mở "
                  f"URL này trên trình duyệt để xem có tải được không.)")
            continue

        try:
            parsed = feedparser.parse(resp.content)
            source_name = parsed.feed.get("title", feed_url) if hasattr(parsed, "feed") else feed_url
            raw_count = len(parsed.entries)

            if verbose:
                bozo_note = f", bozo={parsed.bozo}"
                if getattr(parsed, "bozo", 0):
                    bozo_note += f" ({parsed.bozo_exception})"
                print(f"🔎 {feed_url} → HTTP {resp.status_code}, {raw_count} mục thô{bozo_note}")

            if raw_count == 0:
                print(f"⚠️  Feed {feed_url} trả về 0 mục sau khi tải thành công (HTTP "
                      f"{resp.status_code}) — có thể server trả về trang chặn/lỗi thay vì "
                      f"XML thật, hoặc feed đã đổi cấu trúc. Thử mở URL này trực tiếp trên "
                      f"trình duyệt để kiểm tra nội dung thật sự nhận được.")
                continue

            for entry in parsed.entries:
                title = getattr(entry, "title", "").strip()
                if not title or title in seen_titles:
                    continue
                if not _is_relevant(title):
                    continue

                published = _parse_published(entry)
                if published is None or published < cutoff:
                    continue

                seen_titles.add(title)
                items.append(NewsItem(
                    title=title,
                    source=source_name,
                    published=published,
                    link=getattr(entry, "link", ""),
                ))
        except Exception as e:
            print(f"⚠️  Lỗi xử lý feed {feed_url}: {e} — bỏ qua, tiếp tục feed khác.")
            continue

    items.sort(key=lambda x: x.published, reverse=True)
    return items


if __name__ == "__main__":
    # Chạy thử độc lập: python news_fetcher.py
    news = fetch_recent_news(verbose=True)
    print(f"\nTìm thấy {len(news)} tin liên quan trong {Config.NEWS_LOOKBACK_HOURS} giờ gần nhất:\n")
    for n in news:
        print(f"[{n.published.strftime('%Y-%m-%d %H:%M UTC')}] ({n.source}) {n.title}")