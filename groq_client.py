"""
groq_client.py — Wrapper gọi Groq API cho chat tiếng Việt và diễn giải tín hiệu
"""

from groq import Groq
from config import Config

client = Groq(api_key=Config.GROQ_API_KEY)

SYSTEM_PROMPT = """Bạn là trợ lý phân tích thị trường vàng (XAUUSD) của một bot giao dịch cá nhân.
Luôn trả lời bằng tiếng Việt, ngắn gọn, đúng trọng tâm.
Bạn có thể giải thích thuật ngữ SMC (Order Block, FVG, BOS, CHoCH), price action,
và diễn giải tín hiệu bot đưa ra. Không đưa ra lời khuyên đầu tư tuyệt đối,
chỉ diễn giải dữ liệu và phân tích kỹ thuật."""


def chat(user_message: str, context: str = "") -> str:
    """Chat tự do với Groq, có thể kèm context (vd: dữ liệu tín hiệu gần nhất)."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        messages.append({"role": "system", "content": f"Ngữ cảnh hiện tại: {context}"})
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model=Config.GROQ_MODEL,
        messages=messages,
        temperature=0.4,
        max_tokens=600,
    )
    return response.choices[0].message.content


def explain_signal(signal: dict) -> str:
    """Nhờ Groq viết lại tín hiệu kỹ thuật thành đoạn giải thích tự nhiên bằng tiếng Việt."""
    prompt = f"""Hãy viết một đoạn ngắn (3-5 câu) giải thích tín hiệu giao dịch sau cho người
mới, bằng tiếng Việt, giọng điệu chuyên nghiệp nhưng dễ hiểu:

Hướng: {signal['direction']}
Entry: {signal['entry']}
Stop Loss: {signal['sl']}
Take Profit: {signal['tp']}
Điểm hợp lưu: {signal['score']}/4
Lý do kỹ thuật: {'; '.join(signal['reasons'])}
"""
    return chat(prompt)
