"""
strategy/confluence.py — Chấm điểm hợp lưu đa khung thời gian, ra quyết định entry

4 lớp chấm điểm:
  1. Structure (H4/H1)   — BOS/CHoCH đúng hướng
  2. Order Block / FVG    — giá đang test lại vùng quan tâm
  3. Price Action (M15/M5) — nến xác nhận tại vùng đó
  4. Trigger (M1)          — break nhỏ xác nhận hướng vào lệnh
"""

from strategy.structure import (
    detect_structure_break,
    find_order_blocks,
    find_fair_value_gaps,
    price_in_zone,
)
from strategy.price_action import analyze_price_action


def analyze_confluence(candles: dict, current_price: float) -> dict:
    """
    candles: dict với keys "H4", "H1", "M15", "M5", "M1" -> DataFrame
    Trả về dict: {score, direction, reasons: [...], zone: {...} hoặc None}
    """
    score = 0
    reasons = []
    direction = None

    # --- Lớp 1: Structure trên H4 + H1 ---
    h4_structure = detect_structure_break(candles["H4"])
    h1_structure = detect_structure_break(candles["H1"])

    if h4_structure["direction"] and h4_structure["direction"] == h1_structure["direction"]:
        direction = h4_structure["direction"]
        score += 1
        reasons.append(
            f"Cấu trúc H4+H1 đồng thuận {h4_structure['type']} hướng "
            f"{'TĂNG' if direction == 'bullish' else 'GIẢM'}"
        )
    elif h1_structure["direction"]:
        direction = h1_structure["direction"]
        score += 0.5
        reasons.append(f"Cấu trúc H1 có {h1_structure['type']} hướng "
                        f"{'TĂNG' if direction == 'bullish' else 'GIẢM'} (chưa xác nhận trên H4)")

    if direction is None:
        return {"score": 0, "direction": None, "reasons": ["Chưa có cấu trúc rõ ràng"], "zone": None}

    # --- Lớp 2: Order Block / FVG trên H1 ---
    order_blocks = find_order_blocks(candles["H1"])
    fvgs = find_fair_value_gaps(candles["H1"])

    matching_type = "bullish_ob" if direction == "bullish" else "bearish_ob"
    matching_fvg_type = "bullish_fvg" if direction == "bullish" else "bearish_fvg"

    active_zone = None
    for ob in order_blocks:
        if ob["type"] == matching_type and price_in_zone(current_price, ob["top"], ob["bottom"]):
            active_zone = ob
            score += 1
            reasons.append(f"Giá đang test lại Order Block {matching_type} ({ob['bottom']:.2f}-{ob['top']:.2f})")
            break

    if active_zone is None:
        for fvg in fvgs:
            if fvg["type"] == matching_fvg_type and price_in_zone(current_price, fvg["top"], fvg["bottom"]):
                active_zone = fvg
                # FVG cho +0.5 thay vì +1 (thấp hơn Order Block) — backtest 105 lệnh
                # (2026-08-26) cho thấy Order Block win rate 66.1% trong khi FVG chỉ 52.2%,
                # gần sát coinflip. Order Block vẫn giữ +1 ở nhánh phía trên.
                score += 0.5
                reasons.append(f"Giá đang lấp Fair Value Gap ({fvg['bottom']:.2f}-{fvg['top']:.2f})")
                break

    # --- Lớp 3: Price Action trên M15 + M5 ---
    zone_top = active_zone["top"] if active_zone else None
    zone_bottom = active_zone["bottom"] if active_zone else None

    pa_m15 = analyze_price_action(candles["M15"], zone_top, zone_bottom)
    pa_m5 = analyze_price_action(candles["M5"], zone_top, zone_bottom)

    pa_signals = [pa_m15["pin_bar"], pa_m15["engulfing"], pa_m15["rejection"],
                  pa_m5["pin_bar"], pa_m5["engulfing"], pa_m5["rejection"]]
    expected_prefix = "bullish" if direction == "bullish" else "bearish"
    matching_pa = [s for s in pa_signals if s and s.startswith(expected_prefix)]

    if matching_pa:
        # Ưu tiên pattern "rejection": backtest 105 lệnh (2026-08-26) cho thấy các
        # pattern rejection (bullish/bearish) đạt ~71-85% win rate, trong khi
        # bullish_engulfing/bullish_pin_bar đứng riêng lẻ chỉ 30-38.5% (mẫu 10-13
        # lệnh, còn nhỏ nên đây là ước lượng, không phải kết luận chắc chắn).
        # engulfing/pin_bar đứng một mình vẫn được tính nhưng chỉ +0.5, để không
        # loại bỏ hoàn toàn (thiếu dữ liệu để khẳng định chúng vô dụng), trong khi
        # rejection (một mình hoặc kết hợp) vẫn được +1 đầy đủ như cũ.
        has_rejection = any("rejection" in s for s in matching_pa)
        score += 1 if has_rejection else 0.5
        reasons.append(f"Price action xác nhận: {', '.join(set(matching_pa))}")

    # --- Lớp 4: Trigger trên M1 ---
    m1_structure = detect_structure_break(candles["M1"], lookback=2)
    if m1_structure["direction"] == direction:
        score += 1
        reasons.append(f"M1 có break nhỏ xác nhận hướng vào lệnh ({m1_structure['type']})")

    return {
        "score": round(score, 1),
        "direction": direction,
        "reasons": reasons,
        "zone": active_zone,
    }


def build_signal(analysis: dict, current_price: float, min_score: int) -> dict | None:
    """Chuyển kết quả confluence thành tín hiệu entry hoàn chỉnh (nếu đạt ngưỡng)."""
    if analysis["score"] < min_score or analysis["direction"] is None:
        return None

    direction = analysis["direction"]
    zone = analysis["zone"]

    if zone:
        sl_buffer = (zone["top"] - zone["bottom"]) * 0.5
        if direction == "bullish":
            sl = zone["bottom"] - sl_buffer
            entry = current_price
            tp = entry + (entry - sl) * 2  # R:R mặc định 1:2
        else:
            sl = zone["top"] + sl_buffer
            entry = current_price
            tp = entry - (sl - entry) * 2
    else:
        # Không có zone cụ thể — dùng buffer % mặc định
        buffer = current_price * 0.002
        if direction == "bullish":
            entry, sl = current_price, current_price - buffer
            tp = entry + (entry - sl) * 2
        else:
            entry, sl = current_price, current_price + buffer
            tp = entry - (sl - entry) * 2

    return {
        "direction": "BUY" if direction == "bullish" else "SELL",
        "entry": round(entry, 2),
        "sl": round(sl, 2),
        "tp": round(tp, 2),
        "score": analysis["score"],
        "reasons": analysis["reasons"],
    }