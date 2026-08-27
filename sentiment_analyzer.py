"""
sentiment_analyzer.py — Dùng Groq để chấm sentiment tổng hợp cho vàng dựa trên tin tức.

QUAN TRỌNG (Phase 1.5): kết quả sentiment ở đây CHƯA được cộng vào MIN_CONFLUENCE_SCORE
trong strategy/confluence.py. Mục đích hiện tại chỉ là THU THẬP DỮ LIỆU song song — ghi lại
sentiment tại các thời điểm có tín hiệu kỹ thuật, để sau này (khi đủ mẫu) đối chiếu xem
sentiment có thực sự cải thiện win rate hay không, giống cách đã làm với OB/FVG/price action
ở Phase 1. KHÔNG trộn thẳng vào điểm số khi chưa có bằng chứng — tránh lặp lại rủi ro
overfit đã gặp trước đó.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from groq import Groq

from config import Config
from news_fetcher import NewsItem

client = Groq(api_key=Config.GROQ_API_KEY)

SENTIMENT_SYSTEM_PROMPT = """Bạn là chuyên gia phân tích tin tức vĩ mô cho thị trường vàng (XAUUSD).
Nhiệm vụ: đọc danh sách tiêu đề tin tức gần đây, đánh giá tác động tổng thể tới giá vàng.

Nguyên tắc:
- Lãi suất Fed tăng / kỳ vọng tăng, USD mạnh lên, lạm phát hạ nhiệt → thường TIÊU CỰC cho vàng (bearish)
- Lãi suất Fed giảm / kỳ vọng giảm, USD yếu đi, lạm phát cao, bất ổn địa chính trị, khủng hoảng
  kinh tế, dòng tiền trú ẩn an toàn → thường TÍCH CỰC cho vàng (bullish)
- Tin không liên quan trực tiếp hoặc tác động không rõ ràng → NEUTRAL
- Nếu tin tức mâu thuẫn nhau, đánh giá theo tin nào có ảnh hưởng mạnh hơn (Fed, CPI, NFP quan
  trọng hơn tin phụ)

CHỈ trả lời bằng JSON hợp lệ, không kèm text nào khác, đúng format:
{
  "label": "bullish" | "bearish" | "neutral",
  "score": <số thực từ -1.0 (rất bearish) đến 1.0 (rất bullish)>,
  "reasoning": "<1-2 câu tiếng Việt giải thích ngắn gọn>",
  "key_headline": "<tiêu đề có ảnh hưởng lớn nhất, hoặc rỗng nếu không có>"
}"""


@dataclass
class SentimentResult:
    label: str          # "bullish" | "bearish" | "neutral"
    score: float         # -1.0 .. 1.0
    reasoning: str
    key_headline: str
    num_headlines: int


def _fallback_neutral(num_headlines: int, reason: str) -> SentimentResult:
    return SentimentResult(
        label="neutral", score=0.0,
        reasoning=f"Không đánh giá được ({reason}) — coi như trung lập.",
        key_headline="", num_headlines=num_headlines,
    )


def analyze_sentiment(news_items: list[NewsItem]) -> SentimentResult:
    """Gửi danh sách tin tức cho Groq, trả về SentimentResult.

    Nếu không có tin nào hoặc gọi Groq lỗi, trả về sentiment "neutral" mặc định
    (an toàn — không để lỗi ở module phụ này làm gián đoạn vòng lặp phân tích giá chính).
    """
    if not news_items:
        return _fallback_neutral(0, "không có tin mới trong khung giờ theo dõi")

    headlines_text = "\n".join(
        f"- [{item.published.strftime('%Y-%m-%d %H:%M UTC')}] {item.title}"
        for item in news_items
    )
    user_prompt = f"Danh sách tin tức gần đây:\n\n{headlines_text}"

    try:
        response = client.chat.completions.create(
            model=Config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": SENTIMENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)

        label = str(data.get("label", "neutral")).lower()
        if label not in ("bullish", "bearish", "neutral"):
            label = "neutral"
        score = float(data.get("score", 0.0))
        score = max(-1.0, min(1.0, score))  # kẹp trong khoảng [-1, 1] phòng Groq trả lệch

        return SentimentResult(
            label=label,
            score=score,
            reasoning=str(data.get("reasoning", "")).strip(),
            key_headline=str(data.get("key_headline", "")).strip(),
            num_headlines=len(news_items),
        )
    except Exception as e:
        print(f"⚠️  Lỗi gọi Groq để chấm sentiment: {e} — dùng neutral mặc định.")
        return _fallback_neutral(len(news_items), f"lỗi Groq: {e}")


if __name__ == "__main__":
    # Chạy thử độc lập: python sentiment_analyzer.py
    from news_fetcher import fetch_recent_news

    news = fetch_recent_news()
    result = analyze_sentiment(news)
    print(f"Sentiment: {result.label.upper()} (score={result.score:+.2f}, "
          f"dựa trên {result.num_headlines} tin)")
    print(f"Lý do: {result.reasoning}")
    if result.key_headline:
        print(f"Tin ảnh hưởng nhất: {result.key_headline}")
