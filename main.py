"""
main.py — Vòng lặp chính: quét giá liên tục, phân tích confluence, gửi tín hiệu Telegram

Chạy: python main.py
"""

import asyncio
import logging
import logging.handlers
import os
import time
from datetime import datetime

from config import Config
from mt5_connector import MT5Connector
from strategy.confluence import analyze_confluence, build_signal
import telegram_bot
import sentiment_logger
import calendar_fetcher
import live_signal_logger


def setup_logging() -> logging.Logger:
    """Ghi lại TOÀN BỘ output của bot (kể cả các dòng 'Chưa đủ điều kiện entry' mà
    trước đây chỉ print() ra console và mất luôn khi đóng terminal) vào file, theo
    ngày, tự động dọn file cũ sau 30 ngày để không phình ổ cứng vô hạn.

    Vẫn in ra console y hệt như trước — chỉ THÊM chỗ lưu, không bớt gì.
    """
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger("gold_bot")
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter("%(message)s")

    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join("logs", "bot.log"),
        when="midnight",
        backupCount=30,      # giữ 30 ngày gần nhất, tự xoá file cũ hơn
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


logger = setup_logging()


async def analysis_loop(mt5_conn: MT5Connector):
    last_signal_direction = None
    last_signal_time = None

    await telegram_bot.send_message("🟢 Bot đã khởi động — bắt đầu theo dõi XAUUSD.")

    while True:
        try:
            candles = mt5_conn.get_all_timeframes()
            price_info = mt5_conn.get_current_price()
            current_price = (price_info["bid"] + price_info["ask"]) / 2

            analysis = analyze_confluence(candles, current_price)
            signal = build_signal(analysis, current_price, Config.MIN_CONFLUENCE_SCORE)

            if signal:
                # Tránh spam tín hiệu trùng hướng liên tục trong thời gian ngắn
                now = datetime.now()
                is_duplicate = (
                    last_signal_direction == signal["direction"]
                    and last_signal_time
                    and (now - last_signal_time).total_seconds() < 900  # 15 phút
                )
                if not is_duplicate:
                    logger.info(f"[{now}] 🔔 Tín hiệu {signal['direction']} — điểm {signal['score']}")
                    # Phase 1.5: đính kèm sentiment gần nhất (chỉ tham khảo, xem
                    # telegram_bot.send_signal / sentiment_logger.py để biết lý do
                    # chưa cộng vào điểm số).
                    sentiment = sentiment_logger.get_latest_sentiment()
                    # Phase 1.5b: cảnh báo nếu sắp có tin ảnh hưởng cao (FOMC/CPI/NFP...)
                    # trong vài giờ tới — CHỈ CẢNH BÁO, không tự động huỷ/chặn tín hiệu.
                    try:
                        upcoming_events = calendar_fetcher.get_upcoming_high_impact()
                    except Exception as e:
                        logger.warning(f"⚠️  Lỗi lấy lịch kinh tế: {e}")
                        upcoming_events = []

                    # Ghi ra CSV TRƯỚC khi gửi Telegram: nếu gửi Telegram lỗi/timeout,
                    # tín hiệu vẫn được lưu lại trên đĩa để không mất dấu.
                    try:
                        live_signal_logger.log_signal(signal, sentiment=sentiment)
                    except Exception as e:
                        logger.warning(f"⚠️  Lỗi ghi live_signals_log.csv: {e}")

                    await telegram_bot.send_signal(signal, sentiment=sentiment,
                                                    upcoming_events=upcoming_events)
                    last_signal_direction = signal["direction"]
                    last_signal_time = now
            else:
                logger.info(f"[{datetime.now()}] Chưa đủ điều kiện entry "
                            f"(điểm hiện tại: {analysis['score']}/4)")

        except Exception as e:
            logger.error(f"❌ Lỗi trong vòng lặp phân tích: {e}")

        await asyncio.sleep(Config.CHECK_INTERVAL_SECONDS)


async def main():
    Config.validate()

    mt5_conn = MT5Connector()
    mt5_conn.connect()

    chat_app = telegram_bot.build_chat_app()

    async with chat_app:
        await chat_app.start()
        await chat_app.updater.start_polling()
        try:
            # Chạy song song: vòng lặp phân tích giá (chính) + vòng lặp sentiment tin tức
            # (phụ, Phase 1.5). Nếu sentiment_loop lỗi liên tục, analysis_loop vẫn chạy
            # bình thường — 2 vòng lặp độc lập nhau hoàn toàn.
            await asyncio.gather(
                analysis_loop(mt5_conn),
                sentiment_logger.sentiment_loop(),
            )
        finally:
            await chat_app.updater.stop()
            await chat_app.stop()
            mt5_conn.disconnect()


if __name__ == "__main__":
    asyncio.run(main())