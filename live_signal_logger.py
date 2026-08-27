"""
live_signal_logger.py — Ghi lại MỌI tín hiệu live vào CSV, ngay tại thời điểm gửi Telegram.

Vì sao cần file này (không có trước đây):
main.py trước đây chỉ print() ra console và gửi Telegram khi có tín hiệu — không có
bản ghi nào tồn tại lâu dài trên đĩa. Nếu tắt bot (Ctrl+C, mất điện, restart Windows...),
toàn bộ lịch sử tín hiệu live biến mất, không thể đối chiếu sau này với sentiment_log.csv
hay so sánh với kết quả backtest — đúng mục tiêu bạn đã đặt ra trong NHAT_KY_TIEN_DO.md.

Nguyên tắc an toàn dữ liệu (giống hệt sentiment_logger.py):
- KHÔNG giữ file mở xuyên suốt vòng lặp.
- Mỗi lần có tín hiệu: mở file (mode "a") -> ghi 1 dòng -> đóng file ngay trong cùng
  block `with`. Python flush + đóng file handle trước khi trả quyền điều khiển lại
  cho main.py, nên nếu Ctrl+C xảy ra ngay SAU khi ghi xong, dòng đó vẫn an toàn trên đĩa.
  Rủi ro duy nhất còn lại: nếu Ctrl+C xảy ra ĐÚNG lúc đang ghi dở 1 dòng (cực hiếm, cửa sổ
  thời gian chỉ vài mili-giây) — không có cách nào loại bỏ 100% rủi ro này trong Python
  thường (cần đến file locking/WAL như database), nhưng với tần suất tín hiệu thưa (vài
  chục phút/lần) thì xác suất trùng đúng khoảnh khắc đó gần như bằng 0.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime

LOG_FILE = "live_signals_log.csv"

_HEADERS = [
    "timestamp", "direction", "score", "entry", "sl", "tp", "reasons",
    "sentiment_label", "sentiment_score",
]


def _ensure_log_header():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(_HEADERS)


def log_signal(signal: dict, sentiment=None):
    """Gọi ngay khi main.py quyết định gửi 1 tín hiệu Telegram (sau bước lọc trùng lặp
    is_duplicate, để log khớp đúng số tín hiệu thực sự đã gửi cho người dùng)."""
    _ensure_log_header()
    with open(LOG_FILE, "a", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerow([
            datetime.now().isoformat(timespec="seconds"),
            signal.get("direction"),
            signal.get("score"),
            signal.get("entry"),
            signal.get("sl"),
            signal.get("tp"),
            " | ".join(signal.get("reasons", [])),
            getattr(sentiment, "label", ""),
            getattr(sentiment, "score", ""),
        ])