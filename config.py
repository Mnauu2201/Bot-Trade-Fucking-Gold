"""
config.py — Đọc toàn bộ cấu hình từ file .env
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # --- MT5 ---
    MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
    MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
    MT5_SERVER = os.getenv("MT5_SERVER", "")
    MT5_SYMBOL = os.getenv("MT5_SYMBOL", "XAUUSD")

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # --- Groq ---
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    # --- Bot behavior ---
    CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))
    # float vì score chấm theo bước 0.5 (vd 3.5) — trước đây dùng int() nên
    # MIN_CONFLUENCE_SCORE=3.5 trong .env bị ép về 3, làm ngưỡng lọc không có tác dụng.
    # Nâng mặc định lên 3.5: backtest gộp 7 giai đoạn (204 tín hiệu) cho thấy score=3.0
    # win rate chỉ 54.5% (145 lệnh) trong khi score=3.5 đạt 75.0% (16 lệnh, mẫu còn nhỏ
    # nhưng chênh lệch rõ) — xem md/NHAT_KY_TIEN_DO.md phần "Phân tích ngưỡng điểm".
    MIN_CONFLUENCE_SCORE = float(os.getenv("MIN_CONFLUENCE_SCORE", "3.5"))

    # --- Phase 1.5: Tin tức vĩ mô + Sentiment (Groq) ---
    # CHƯA cộng vào MIN_CONFLUENCE_SCORE — chỉ log song song để đối chiếu sau này.
    # LỊCH SỬ: bản trước dùng dailyforex.com/rss/forexnews.xml — đã xác nhận (2026-08-27)
    # URL này trả về 404 thật (feed đã đổi/gỡ bỏ), không phải lỗi mạng — đã bỏ, thay bằng
    # investinglive.com/feed (feed chính, nhiều tin hơn /feed/centralbank/ cũ, đã xác nhận
    # có tin gold/Fed/inflation mới liên tục). Cả 2 feed dưới đây đã xác nhận sống và có
    # dữ liệu thật tính đến 2026-08-27. Nếu 1 feed lỗi, code tự bỏ qua và dùng feed còn lại.
    #
    # LƯU Ý QUAN TRỌNG VỀ MẠNG (đã xác nhận qua chẩn đoán 2026-08-27): nếu vẫn thấy lỗi
    # ConnectionResetError/Read timed out dù feed URL đúng, đây thường là do ISP chặn theo
    # SNI (đọc được tên miền ngay trong bước bắt tay TLS ban đầu dù đã đổi DNS sang
    # 8.8.8.8/1.1.1.1 — đổi DNS thường không đủ vì SNI vẫn lộ ở tầng TCP/TLS, không phải
    # tầng DNS). Cách xử lý đã kiểm chứng: cài Cloudflare WARP (https://1.1.1.1/) và bật
    # chế độ "1.1.1.1 with WARP" — WARP mã hoá toàn bộ traffic qua tunnel nên ISP không
    # đọc được SNI để chặn nữa. Đây KHÔNG phải lỗi do Kaspersky hay do code — đã loại trừ
    # cả hai khả năng đó trong quá trình chẩn đoán trước khi xác định đúng nguyên nhân.
    _DEFAULT_NEWS_FEEDS = (
        "https://www.fxstreet.com/rss/news,"  # FXStreet - tin forex/vàng tổng hợp, đã xác nhận sống 2026-08-27
        "https://investinglive.com/feed"      # investingLive - feed chính (không phải /feed/centralbank/), đã xác nhận sống + nhiều tin gold/Fed 2026-08-27
    )
    NEWS_RSS_FEEDS = [
        f.strip() for f in os.getenv("NEWS_RSS_FEEDS", _DEFAULT_NEWS_FEEDS).split(",") if f.strip()
    ]
    NEWS_KEYWORDS = [
        kw.strip() for kw in os.getenv(
            "NEWS_KEYWORDS",
            "gold,xau,fed,interest rate,inflation,cpi,nfp,payroll,dollar,fomc,rate cut,"
            "rate hike,recession,jobless,treasury,yield,oil,geopolit"
        ).split(",") if kw.strip()
    ]
    NEWS_LOOKBACK_HOURS = int(os.getenv("NEWS_LOOKBACK_HOURS", "6"))
    NEWS_CHECK_INTERVAL_SECONDS = int(os.getenv("NEWS_CHECK_INTERVAL_SECONDS", "1800"))  # 30 phút

    # --- Phase 1.5b: Lịch kinh tế ForexFactory (tin "đỏ"/high-impact) ---
    # ForexFactory đã đóng feed RSS/XML chính thức — URL dưới đây là mirror do Fair Economy
    # (công ty sở hữu ForexFactory) vận hành, được cộng đồng EA dùng phổ biến nhiều năm.
    # LƯU Ý: domain này từng có tiền tố "cdn-" (cdn-nfs.faireconomy.media) nhưng đã đổi
    # thành "nfs.faireconomy.media" (bỏ "cdn-") từ tháng 3/2021 — đã xác nhận domain hiện
    # tại (2026-08-27) hoạt động và đúng cấu trúc XML code này parse.
    # ForexFactory giới hạn tải file lịch tuần tối đa ~2 lần/5 phút — CALENDAR_CACHE_TTL_SECONDS
    # mặc định 3600s (1 giờ) đã an toàn, không nên giảm xuống quá thấp (dưới vài phút) kẻo
    # bị chặn IP tạm thời.
    CALENDAR_XML_URL = os.getenv(
        "CALENDAR_XML_URL", "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
    )
    # Vàng chủ yếu phản ứng với dữ liệu kinh tế Mỹ (USD) — mặc định chỉ lọc USD.
    # Có thể thêm EUR/CNY/... nếu muốn theo dõi rộng hơn.
    CALENDAR_CURRENCIES = [
        c.strip() for c in os.getenv("CALENDAR_CURRENCIES", "USD").split(",") if c.strip()
    ]
    CALENDAR_LOOKAHEAD_HOURS = float(os.getenv("CALENDAR_LOOKAHEAD_HOURS", "2"))
    CALENDAR_CACHE_TTL_SECONDS = int(os.getenv("CALENDAR_CACHE_TTL_SECONDS", "3600"))  # 1 giờ
    # Giờ trong XML của Fair Economy là giờ Mỹ (Eastern Time, tự lệch theo DST), KHÔNG
    # phải giờ local của máy bạn. Trước đây code bỏ qua timezone này hoàn toàn (bug: so
    # sánh datetime naive ET với datetime.now() giờ VN, lệch ~11 tiếng) — giờ đã sửa để
    # gắn đúng timezone nguồn trước khi so sánh. Không cần đổi giá trị này trừ khi Fair
    # Economy đổi timezone gốc của feed XML.
    CALENDAR_ASSUMED_TZ = os.getenv("CALENDAR_ASSUMED_TZ", "America/New_York")

    @classmethod
    def validate(cls):
        missing = []
        if not cls.MT5_LOGIN:
            missing.append("MT5_LOGIN")
        if not cls.MT5_PASSWORD:
            missing.append("MT5_PASSWORD")
        if not cls.MT5_SERVER:
            missing.append("MT5_SERVER")
        if not cls.TELEGRAM_BOT_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not cls.TELEGRAM_CHAT_ID:
            missing.append("TELEGRAM_CHAT_ID")
        if not cls.GROQ_API_KEY:
            missing.append("GROQ_API_KEY")

        if missing:
            raise ValueError(
                f"Thiếu cấu hình trong file .env: {', '.join(missing)}. "
                f"Xem lại mục 7 trong HUONG_DAN_SETUP.md"
            )