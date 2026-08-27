"""
sentiment_logger.py — Vòng lặp nền: định kỳ lấy tin tức + chấm sentiment, ghi vào CSV.

Đây là vòng lặp ĐỘC LẬP với analysis_loop (vòng lặp phân tích giá chính trong main.py):
chạy song song, không chặn nhau, không ảnh hưởng đến việc tính confluence score.

Mục đích: sau vài tuần/tháng thu thập, sentiment_log.csv sẽ có đủ dữ liệu để đối chiếu
với backtest_report_*.csv (theo timestamp gần nhất) — trả lời câu hỏi "sentiment tại thời
điểm tín hiệu nổ ra có tương quan với việc lệnh đó thắng/thua không?" TRƯỚC KHI quyết định
có nên cộng sentiment vào MIN_CONFLUENCE_SCORE hay không.
"""

from __future__ import annotations

import asyncio
import csv
import os
from datetime import datetime

from config import Config
from news_fetcher import fetch_recent_news
from sentiment_analyzer import analyze_sentiment, SentimentResult

LOG_FILE = "sentiment_log.csv"

_latest_sentiment: SentimentResult | None = None  # cache để main.py đọc khi gửi tín hiệu


def get_latest_sentiment() -> SentimentResult | None:
    """main.py gọi hàm này khi gửi tín hiệu Telegram, để đính kèm sentiment gần nhất
    (chỉ mang tính tham khảo, KHÔNG ảnh hưởng đến điểm confluence đã tính)."""
    return _latest_sentiment


def _ensure_log_header():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "label", "score", "num_headlines", "reasoning", "key_headline"
            ])


def _append_log(result: SentimentResult):
    _ensure_log_header()
    with open(LOG_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().isoformat(timespec="seconds"),
            result.label,
            f"{result.score:.2f}",
            result.num_headlines,
            result.reasoning,
            result.key_headline,
        ])


async def sentiment_loop():
    """Chạy song song với analysis_loop qua asyncio.gather() trong main.py."""
    global _latest_sentiment

    while True:
        try:
            news = fetch_recent_news()
            result = analyze_sentiment(news)
            _latest_sentiment = result
            _append_log(result)

            print(f"[{datetime.now()}] 📰 Sentiment: {result.label.upper()} "
                  f"(score={result.score:+.2f}, {result.num_headlines} tin) — {result.reasoning}")
        except Exception as e:
            # Lỗi ở module phụ này không được phép làm crash bot chính
            print(f"❌ Lỗi trong sentiment_loop: {e}")

        await asyncio.sleep(Config.NEWS_CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    # Chạy thử độc lập, in liên tục — Ctrl+C để dừng: python sentiment_logger.py
    asyncio.run(sentiment_loop())
