"""
strategy/structure.py — Phát hiện cấu trúc thị trường (Smart Money Concept)

- Swing High/Low
- BOS (Break of Structure) / CHoCH (Change of Character)
- Order Block (vùng nến cuối cùng trước cú break mạnh)
- Fair Value Gap (khoảng trống giá 3 nến)
"""

import pandas as pd


def find_swing_points(df: pd.DataFrame, lookback: int = 3) -> pd.DataFrame:
    """Đánh dấu các đỉnh/đáy swing (swing high/low) đơn giản bằng so sánh lân cận."""
    df = df.copy()
    df["swing_high"] = False
    df["swing_low"] = False

    for i in range(lookback, len(df) - lookback):
        window_high = df["high"].iloc[i - lookback:i + lookback + 1]
        window_low = df["low"].iloc[i - lookback:i + lookback + 1]

        if df["high"].iloc[i] == window_high.max():
            df.at[df.index[i], "swing_high"] = True
        if df["low"].iloc[i] == window_low.min():
            df.at[df.index[i], "swing_low"] = True

    return df


def detect_structure_break(df: pd.DataFrame, lookback: int = 3) -> dict:
    """
    Phát hiện BOS/CHoCH gần nhất.
    Trả về: {"type": "BOS"/"CHoCH"/None, "direction": "bullish"/"bearish"/None}
    """
    df = find_swing_points(df, lookback)
    swing_highs = df[df["swing_high"]].tail(3)
    swing_lows = df[df["swing_low"]].tail(3)

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return {"type": None, "direction": None}

    last_close = df["close"].iloc[-1]
    last_swing_high = swing_highs["high"].iloc[-1]
    last_swing_low = swing_lows["low"].iloc[-1]
    prev_swing_high = swing_highs["high"].iloc[-2]
    prev_swing_low = swing_lows["low"].iloc[-2]

    # Break lên trên swing high gần nhất -> có thể là BOS/CHoCH tăng
    if last_close > last_swing_high:
        structure_type = "CHoCH" if prev_swing_high > last_swing_high else "BOS"
        return {"type": structure_type, "direction": "bullish"}

    # Break xuống dưới swing low gần nhất -> có thể là BOS/CHoCH giảm
    if last_close < last_swing_low:
        structure_type = "CHoCH" if prev_swing_low < last_swing_low else "BOS"
        return {"type": structure_type, "direction": "bearish"}

    return {"type": None, "direction": None}


def find_order_blocks(df: pd.DataFrame, min_move_pct: float = 0.15) -> list:
    """
    Tìm Order Block: nến ngược hướng cuối cùng trước một cú di chuyển mạnh.
    min_move_pct: % biến động tối thiểu (so với giá) để coi là "cú di chuyển mạnh".
    """
    order_blocks = []
    for i in range(1, len(df) - 1):
        move_pct = abs(df["close"].iloc[i] - df["open"].iloc[i]) / df["open"].iloc[i] * 100
        if move_pct < min_move_pct:
            continue

        is_bullish_move = df["close"].iloc[i] > df["open"].iloc[i]
        prev_candle = df.iloc[i - 1]
        prev_is_bearish = prev_candle["close"] < prev_candle["open"]
        prev_is_bullish = prev_candle["close"] > prev_candle["open"]

        # OB tăng: nến giảm cuối cùng trước cú tăng mạnh
        if is_bullish_move and prev_is_bearish:
            order_blocks.append({
                "type": "bullish_ob",
                "top": prev_candle["open"],
                "bottom": prev_candle["close"],
                "time": prev_candle["time"],
            })
        # OB giảm: nến tăng cuối cùng trước cú giảm mạnh
        elif not is_bullish_move and prev_is_bullish:
            order_blocks.append({
                "type": "bearish_ob",
                "top": prev_candle["close"],
                "bottom": prev_candle["open"],
                "time": prev_candle["time"],
            })

    return order_blocks[-5:]  # chỉ giữ 5 OB gần nhất


def find_fair_value_gaps(df: pd.DataFrame) -> list:
    """
    Fair Value Gap (FVG): khoảng trống giữa nến 1 và nến 3 trong bộ 3 nến liên tiếp,
    khi nến 2 di chuyển mạnh và để lại khoảng trống chưa được lấp.
    """
    fvgs = []
    for i in range(2, len(df)):
        candle1 = df.iloc[i - 2]
        candle3 = df.iloc[i]

        # FVG tăng: đáy nến 3 cao hơn đỉnh nến 1
        if candle3["low"] > candle1["high"]:
            fvgs.append({
                "type": "bullish_fvg",
                "top": candle3["low"],
                "bottom": candle1["high"],
                "time": candle3["time"],
            })
        # FVG giảm: đỉnh nến 3 thấp hơn đáy nến 1
        elif candle3["high"] < candle1["low"]:
            fvgs.append({
                "type": "bearish_fvg",
                "top": candle1["low"],
                "bottom": candle3["high"],
                "time": candle3["time"],
            })

    return fvgs[-5:]  # chỉ giữ 5 FVG gần nhất


def price_in_zone(price: float, zone_top: float, zone_bottom: float, tolerance_pct: float = 0.1) -> bool:
    """Kiểm tra giá hiện tại có đang nằm trong (hoặc gần) một vùng OB/FVG không."""
    tolerance = (zone_top - zone_bottom) * tolerance_pct
    return (zone_bottom - tolerance) <= price <= (zone_top + tolerance)
