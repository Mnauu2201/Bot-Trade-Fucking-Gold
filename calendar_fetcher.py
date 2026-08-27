"""
calendar_fetcher.py — Lấy lịch kinh tế (tin "đỏ"/high-impact) từ ForexFactory.

ForexFactory đã ĐÓNG feed RSS/XML công khai chính thức (forexfactory.com/calendar/rss)
từ lâu để chống bị scrape hàng loạt. URL dùng ở đây (nfs.faireconomy.media) là mirror do
chính công ty sở hữu ForexFactory (Fair Economy) vận hành, được cộng đồng EA/indicator
dùng phổ biến nhiều năm nay. LƯU Ý: domain này từng có tiền tố "cdn-" nhưng đã đổi thành
"nfs.faireconomy.media" (bỏ "cdn-") từ tháng 3/2021 — nếu code này lại báo lỗi DNS/kết
nối trong tương lai, domain có thể đã đổi lần nữa, thử tìm "faireconomy.media ff calendar"
trên Google/forum MQL5/ForexFactory để tìm URL mới nhất.

Không có tài liệu API chính thức nên nếu Fair Economy đổi cấu trúc XML, code này có thể
cần chỉnh lại — chạy `python calendar_fetcher.py` để tự kiểm tra, script sẽ in ra XML thô
nếu parse lỗi.

QUAN TRỌNG về múi giờ: giờ trong feed là giờ Mỹ (Eastern Time, tự động lệch theo DST).
CALENDAR_ASSUMED_TZ trong config.py khai báo timezone nguồn này — code sẽ tự gắn
timezone rồi convert sang giờ local của máy bạn khi so sánh, không cần bạn tự quy đổi.

Mục đích: cảnh báo sắp có tin ảnh hưởng cao (FOMC, CPI, NFP...) để cân nhắc KHÔNG vào
lệnh mới trong khung giờ nhạy cảm — đúng nguyên tắc đã có trong tài liệu tổng hợp của
bạn ("nên đóng lệnh hoặc đứng ngoài thị trường khoảng 15-30 phút trước/sau tin rất cao").
Đây là thông tin CẢNH BÁO đính kèm, KHÔNG tự động chặn tín hiệu — quyết định vẫn ở bạn,
trừ khi sau này bạn muốn nâng cấp thành tự động bỏ qua tín hiệu gần giờ tin.
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from config import Config

# Giờ trong XML là giờ Mỹ (Eastern Time) — gắn timezone này vào lúc parse rồi convert
# sang giờ local của máy khi so sánh, thay vì so sánh naive-với-naive (bug cũ khiến
# lệch ~11 tiếng giữa ET và giờ VN, làm mọi so sánh "trong X giờ tới" sai hoàn toàn).
_SOURCE_TZ = ZoneInfo(Config.CALENDAR_ASSUMED_TZ)

_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
_REQUEST_TIMEOUT_SECONDS = 20
_MAX_RETRIES = 2


@dataclass
class CalendarEvent:
    title: str
    country: str       # mã tiền tệ liên quan, vd "USD", "EUR"
    impact: str         # "High" | "Medium" | "Low" | "Holiday"
    event_time: datetime | None  # None nếu là sự kiện "All Day"/"Tentative" không có giờ cụ thể
    forecast: str = ""
    previous: str = ""


def _fetch_raw_xml() -> str | None:
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.get(Config.CALENDAR_XML_URL, headers=_REQUEST_HEADERS,
                                 timeout=_REQUEST_TIMEOUT_SECONDS)
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Lần {attempt} tải lịch kinh tế lỗi ({e})"
                  + (" — thử lại..." if attempt < _MAX_RETRIES else " — bỏ cuộc."))
            if attempt < _MAX_RETRIES:
                time.sleep(2)
    return None


def _parse_event_time(date_str: str, time_str: str) -> datetime | None:
    """XML gốc tách riêng cột date (vd '08-27-2026') và time (vd '8:30am' hoặc
    'All Day'/'Tentative'/rỗng). Trả về None nếu không có giờ cụ thể."""
    if not date_str or not time_str:
        return None
    time_str_clean = time_str.strip().lower()
    if time_str_clean in ("all day", "tentative", "day 1", "day 2", ""):
        return None
    try:
        combined = f"{date_str.strip()} {time_str.strip().upper()}"
        naive_et = datetime.strptime(combined, "%m-%d-%Y %I:%M%p")
        # Gắn timezone nguồn (ET), rồi convert sang giờ local của máy (aware) — để so
        # sánh với datetime.now(tz=...) sau này luôn đúng, bất kể máy chạy ở múi giờ nào.
        aware_et = naive_et.replace(tzinfo=_SOURCE_TZ)
        return aware_et.astimezone()
    except ValueError:
        return None


def fetch_calendar_events(verbose: bool = False) -> list[CalendarEvent]:
    """Tải và parse toàn bộ sự kiện trong tuần từ ForexFactory calendar XML.

    Trả về danh sách rỗng (không raise) nếu tải lỗi hoặc parse lỗi — module phụ này
    không được phép làm crash bot chính.
    """
    raw = _fetch_raw_xml()
    if raw is None:
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        print(f"⚠️  Không parse được XML lịch kinh tế: {e}")
        print("--- 1000 ký tự đầu của phản hồi nhận được (để đối chiếu cấu trúc thật) ---")
        print(raw[:1000])
        return []

    events: list[CalendarEvent] = []
    event_nodes = root.findall(".//event")

    if verbose:
        print(f"🔎 Tìm thấy {len(event_nodes)} thẻ <event> trong XML")

    for node in event_nodes:
        def _text(tag: str) -> str:
            el = node.find(tag)
            return el.text.strip() if el is not None and el.text else ""

        title = _text("title")
        country = _text("country")
        impact = _text("impact")
        date_str = _text("date")
        time_str = _text("time")
        forecast = _text("forecast")
        previous = _text("previous")

        if not title:
            continue

        events.append(CalendarEvent(
            title=title,
            country=country,
            impact=impact,
            event_time=_parse_event_time(date_str, time_str),
            forecast=forecast,
            previous=previous,
        ))

    return events


_cache: dict = {"events": [], "fetched_at": None}


def _get_events_cached() -> list[CalendarEvent]:
    now = datetime.now()
    if (_cache["fetched_at"] is None
            or (now - _cache["fetched_at"]).total_seconds() > Config.CALENDAR_CACHE_TTL_SECONDS):
        _cache["events"] = fetch_calendar_events()
        _cache["fetched_at"] = now
    return _cache["events"]


def get_upcoming_high_impact(
    events: list[CalendarEvent] | None = None,
    within_hours: float | None = None,
    currencies: list[str] | None = None,
) -> list[CalendarEvent]:
    """Lọc các sự kiện High impact sắp diễn ra trong within_hours giờ tới.

    events=None sẽ dùng cache (tự refresh mỗi CALENDAR_CACHE_TTL_SECONDS, mặc định
    1 giờ) thay vì gọi mạng mỗi lần — lịch kinh tế không đổi liên tục như tin tức nên
    không cần tải lại mỗi vòng lặp giá (60s). currencies=None dùng Config.CALENDAR_CURRENCIES.
    Bỏ qua các sự kiện không có giờ cụ thể (All Day/Tentative) vì không tính được
    khoảng cách thời gian.
    """
    if events is None:
        events = _get_events_cached()
    within_hours = within_hours if within_hours is not None else Config.CALENDAR_LOOKAHEAD_HOURS
    currencies = currencies or Config.CALENDAR_CURRENCIES

    now = datetime.now().astimezone()  # aware, local tz — khớp với event_time cũng đã aware
    window_end = now + timedelta(hours=within_hours)

    upcoming = []
    for ev in events:
        if ev.impact.lower() != "high":
            continue
        if currencies and ev.country.upper() not in [c.upper() for c in currencies]:
            continue
        if ev.event_time is None:
            continue
        if now <= ev.event_time <= window_end:
            upcoming.append(ev)

    upcoming.sort(key=lambda e: e.event_time)
    return upcoming


if __name__ == "__main__":
    # Chạy thử độc lập: python calendar_fetcher.py
    events = fetch_calendar_events(verbose=True)
    print(f"\nTổng số sự kiện trong tuần: {len(events)}")

    now = datetime.now().astimezone()
    print(f"⏰ Giờ hiện tại (đã quy đổi, aware): {now.strftime('%Y-%m-%d %H:%M %z')}")

    upcoming = get_upcoming_high_impact(events)
    print(f"\nSự kiện HIGH impact trong {Config.CALENDAR_LOOKAHEAD_HOURS} giờ tới "
          f"(currencies={Config.CALENDAR_CURRENCIES}):\n")
    if not upcoming:
        print("(không có sự kiện nào trong đúng cửa sổ giờ đang lọc — xem phần DEBUG bên "
              "dưới để biết sự kiện gần nhất còn cách bao lâu)")
    for ev in upcoming:
        print(f"[{ev.event_time.strftime('%Y-%m-%d %H:%M %z')}] {ev.country} — {ev.title} "
              f"(dự báo: {ev.forecast or 'N/A'}, kỳ trước: {ev.previous or 'N/A'})")

    # --- DEBUG: liệt kê TẤT CẢ sự kiện High impact + đúng currency, không giới hạn giờ,
    # để bạn tự đối chiếu với https://www.forexfactory.com/calendar và biết chắc code
    # đang tính đúng hay sai, thay vì chỉ thấy "rỗng" và phải đoán nguyên nhân. ---
    print("\n--- DEBUG: toàn bộ sự kiện High impact + currency phù hợp trong tuần (không lọc giờ) ---")
    target_currencies = [c.upper() for c in Config.CALENDAR_CURRENCIES]
    all_high = [
        ev for ev in events
        if ev.impact.lower() == "high"
        and ev.country.upper() in target_currencies
        and ev.event_time is not None
    ]
    all_high.sort(key=lambda e: e.event_time)
    if not all_high:
        print("(không tìm thấy sự kiện High impact nào khớp currency trong toàn bộ tuần — "
              "kiểm tra lại CALENDAR_CURRENCIES trong .env, hoặc đối chiếu tay với "
              "forexfactory.com/calendar xem tuần này có tin đỏ USD không)")
    for ev in all_high:
        diff_hours = (ev.event_time - now).total_seconds() / 3600
        if diff_hours < 0:
            marker = "⌛ đã qua"
        elif diff_hours <= Config.CALENDAR_LOOKAHEAD_HOURS:
            marker = "✅ SẮP TỚI (trong cửa sổ lọc)"
        else:
            marker = "⏳ còn xa (ngoài cửa sổ lọc)"
        print(f"[{ev.event_time.strftime('%Y-%m-%d %H:%M %z')}] (còn {diff_hours:+.1f}h) "
              f"{marker} — {ev.title}")