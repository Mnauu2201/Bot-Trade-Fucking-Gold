"""
strategy/price_action.py — Nhận diện mô hình nến price action

Các mô hình: Pin Bar / Hammer, Engulfing, Rejection Wick
"""

import pandas as pd


def detect_pin_bar(candle: pd.Series) -> str | None:
    """Pin bar: bóng nến (wick) dài gấp ít nhất 2 lần thân nến, ở 1 phía."""
    body = abs(candle["close"] - candle["open"])
    upper_wick = candle["high"] - max(candle["close"], candle["open"])
    lower_wick = min(candle["close"], candle["open"]) - candle["low"]

    if body == 0:
        return None

    if lower_wick >= body * 2 and lower_wick > upper_wick:
        return "bullish_pin_bar"
    if upper_wick >= body * 2 and upper_wick > lower_wick:
        return "bearish_pin_bar"
    return None


def detect_engulfing(prev_candle: pd.Series, candle: pd.Series) -> str | None:
    """Engulfing: thân nến hiện tại bao trùm hoàn toàn thân nến trước, ngược hướng."""
    prev_bullish = prev_candle["close"] > prev_candle["open"]
    curr_bullish = candle["close"] > candle["open"]

    if prev_bullish and not curr_bullish:
        if candle["open"] >= prev_candle["close"] and candle["close"] <= prev_candle["open"]:
            return "bearish_engulfing"
    if not prev_bullish and curr_bullish:
        if candle["open"] <= prev_candle["close"] and candle["close"] >= prev_candle["open"]:
            return "bullish_engulfing"
    return None


def detect_rejection_wick(candle: pd.Series, zone_top: float, zone_bottom: float) -> str | None:
    """Rejection: giá thò vào vùng quan tâm (OB/FVG) rồi bị đẩy ngược lại, đóng cửa ngoài vùng."""
    touched_zone = candle["low"] <= zone_top and candle["high"] >= zone_bottom
    if not touched_zone:
        return None

    closed_above = candle["close"] > zone_top
    closed_below = candle["close"] < zone_bottom

    if closed_above and candle["low"] <= zone_top:
        return "bullish_rejection"
    if closed_below and candle["high"] >= zone_bottom:
        return "bearish_rejection"
    return None


def analyze_price_action(df: pd.DataFrame, zone_top: float = None, zone_bottom: float = None) -> dict:
    """Phân tích tổng hợp price action trên nến gần nhất."""
    last = df.iloc[-1]
    prev = df.iloc[-2]

    result = {"pin_bar": None, "engulfing": None, "rejection": None}
    result["pin_bar"] = detect_pin_bar(last)
    result["engulfing"] = detect_engulfing(prev, last)

    if zone_top is not None and zone_bottom is not None:
        result["rejection"] = detect_rejection_wick(last, zone_top, zone_bottom)

    return result
