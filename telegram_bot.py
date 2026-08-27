"""
telegram_bot.py — Gửi tín hiệu qua Telegram + trò chuyện tiếng Việt 2 chiều qua Groq
"""

import asyncio
from telegram import Bot, Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from config import Config
import groq_client

bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)

# Lưu tạm bối cảnh tín hiệu gần nhất để trả lời chat có ngữ cảnh
_last_signal_context = {"text": ""}


async def send_message(text: str):
    await bot.send_message(chat_id=Config.TELEGRAM_CHAT_ID, text=text, parse_mode="Markdown")


def format_signal_message(signal: dict) -> str:
    emoji = "🟢" if signal["direction"] == "BUY" else "🔴"
    reasons_text = "\n".join(f"  • {r}" for r in signal["reasons"])
    return (
        f"{emoji} *TÍN HIỆU {signal['direction']} — XAUUSD*\n\n"
        f"📍 Entry: `{signal['entry']}`\n"
        f"🛑 SL: `{signal['sl']}`\n"
        f"🎯 TP: `{signal['tp']}`\n"
        f"⭐ Điểm hợp lưu: {signal['score']}/4\n\n"
        f"*Lý do:*\n{reasons_text}"
    )


async def send_signal(signal: dict, sentiment=None, upcoming_events=None):
    message = format_signal_message(signal)
    _last_signal_context["text"] = message
    await send_message(message)

    # Phase 1.5: đính kèm sentiment tin tức gần nhất — CHỈ THAM KHẢO, không thuộc điểm
    # hợp lưu ở trên và không ảnh hưởng đến việc bot đã ra tín hiệu này hay chưa.
    if sentiment is not None:
        emoji = {"bullish": "📈", "bearish": "📉", "neutral": "⚪"}.get(sentiment.label, "⚪")
        await send_message(
            f"{emoji} _Sentiment tin tức gần đây (tham khảo, không ảnh hưởng điểm số):_\n"
            f"{sentiment.label.upper()} (score {sentiment.score:+.2f}, "
            f"dựa trên {sentiment.num_headlines} tin)\n"
            f"_{sentiment.reasoning}_"
        )

    # Phase 1.5b: cảnh báo nếu sắp có tin kinh tế ảnh hưởng cao (FOMC/CPI/NFP...) —
    # CHỈ CẢNH BÁO để bạn tự cân nhắc, KHÔNG tự động huỷ tín hiệu ở trên.
    if upcoming_events:
        lines = "\n".join(
            f"  • {ev.event_time.strftime('%H:%M')} {ev.country} — {ev.title}"
            for ev in upcoming_events
        )
        await send_message(
            f"⚠️ *Sắp có tin ảnh hưởng cao trong {Config.CALENDAR_LOOKAHEAD_HOURS:.0f} giờ tới:*\n"
            f"{lines}\n\n"
            f"_Cân nhắc không vào lệnh mới hoặc siết SL trước giờ tin — biến động có thể "
            f"quét SL bất thường trước khi đi đúng hướng dự đoán._"
        )

    # Gửi thêm phần diễn giải tự nhiên từ Groq
    try:
        explanation = groq_client.explain_signal(signal)
        await send_message(f"💬 _Giải thích thêm:_\n{explanation}")
    except Exception as e:
        print(f"⚠️ Groq explain lỗi: {e}")


async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi người dùng nhắn tin trực tiếp cho bot (chat tự do tiếng Việt)."""
    user_text = update.message.text
    reply = groq_client.chat(user_text, context=_last_signal_context["text"])
    await update.message.reply_text(reply)


def build_chat_app() -> Application:
    """Dựng app xử lý tin nhắn 2 chiều — chạy song song với vòng lặp phân tích chính."""
    app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))
    return app
