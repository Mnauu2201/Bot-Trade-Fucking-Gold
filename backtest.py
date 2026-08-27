"""
backtest.py — Chạy thử chiến lược confluence trên dữ liệu lịch sử MT5

Tự động mô phỏng: với mỗi tín hiệu đã lẽ ra được gửi trong quá khứ, kiểm tra xem
giá chạm TP trước hay SL trước -> tính ra win rate, R:R thực tế, tổng lệnh.

KHÔNG cần hiểu sâu về trading để đọc kết quả — script tự làm hết, chỉ cần đọc
báo cáo cuối cùng.

Chạy đoạn dữ liệu gần nhất:
    python backtest.py

Chạy một đoạn lịch sử xa hơn (để test qua giai đoạn thị trường khác — quan
trọng vì 1 lần chạy chỉ cho biết chiến lược sống ra sao trong ĐÚNG giai đoạn
đó, không đại diện cho mọi kiểu thị trường):
    python backtest.py --offset 15200
    python backtest.py --offset 30400
    (mỗi lần cộng thêm ~15200 là lùi thêm 1 "đợt" ~10 ngày giao dịch trước đó,
    không trùng lặp với lần chạy trước)

Mỗi lần chạy sẽ tự động ghi thêm 1 dòng tóm tắt vào backtest_runs_log.csv để
theo dõi win rate có ổn định qua nhiều giai đoạn/nhiều lần chạy hay không,
trước khi quyết định vào tiền thật.
"""

import argparse
import math
import os

import pandas as pd
from datetime import datetime
from config import Config
from mt5_connector import MT5Connector
from strategy.confluence import analyze_confluence, build_signal

# --- Cấu hình backtest ---
BACKTEST_CANDLES = 15000   # số nến M1 lùi lại để test (15000 nến M1 ~ 10 ngày giao dịch)
LOOKAHEAD_BARS = 800        # số nến M1 tối đa để chờ xem SL/TP chạm cái nào trước
                            # (nâng từ 200 lên 800 ngày 2026-08-26: dữ liệu 155 lệnh cho thấy
                            # các lệnh TIMEOUT có TP/SL cách entry trung bình ~60$/oz, gấp
                            # 3-4 lần các lệnh đã ngã ngũ (~16-20$/oz) — 200 nến (~3.3 giờ)
                            # quá ngắn để những setup mục tiêu xa này kịp chạm SL/TP, khiến
                            # ~51% tín hiệu bị loại khỏi phép tính win rate một cách thiên
                            # lệch. 800 nến (~13.3 giờ) vẫn nằm an toàn trong BACKTEST_CANDLES
                            # =15000 nến mỗi đợt.
DEDUP_MINUTES = 60          # gộp các tín hiệu cùng hướng cách nhau dưới X phút thành 1 (tránh đếm trùng 1 setup nhiều lần)
MIN_DECIDED_FOR_CONFIDENCE = 50  # dưới ngưỡng này, số liệu chỉ mang tính tham khảo, chưa đủ để tin

RUN_LOG_FILE = "backtest_runs_log.csv"

TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240}


def simulate_trade(future_candles: pd.DataFrame, signal: dict) -> dict:
    """
    Mô phỏng 1 lệnh: quét từng nến tương lai, xem giá chạm SL hay TP trước.
    Trả về: {"result": "WIN"/"LOSS"/"TIMEOUT", "bars_to_result": int}
    """
    direction = signal["direction"]
    sl, tp = signal["sl"], signal["tp"]

    for i, candle in future_candles.iterrows():
        if direction == "BUY":
            if candle["low"] <= sl:
                return {"result": "LOSS", "bars_to_result": i}
            if candle["high"] >= tp:
                return {"result": "WIN", "bars_to_result": i}
        else:  # SELL
            if candle["high"] >= sl:
                return {"result": "LOSS", "bars_to_result": i}
            if candle["low"] <= tp:
                return {"result": "WIN", "bars_to_result": i}

    return {"result": "TIMEOUT", "bars_to_result": len(future_candles)}


def run_backtest(offset_bars: int = 0, backtest_candles: int = BACKTEST_CANDLES):
    print("📊 Đang tải dữ liệu lịch sử từ MT5...")
    if offset_bars > 0:
        print(f"   (đang test đoạn lịch sử lùi {offset_bars} nến M1 so với hiện tại — "
              f"không phải đoạn gần nhất)")
    mt5_conn = MT5Connector()
    mt5_conn.connect()

    # Quy đổi offset (tính theo nến M1) sang số nến tương ứng cho từng khung thời gian,
    # để tất cả các khung đều bắt đầu cùng 1 mốc thời gian trong quá khứ.
    offset_minutes = offset_bars

    def tf_offset(tf: str) -> int:
        return offset_minutes // TF_MINUTES[tf]

    # Lấy dữ liệu đủ lớn cho mỗi khung thời gian
    h4 = mt5_conn.get_candles("H4", backtest_candles // 4, offset=tf_offset("H4"))
    h1 = mt5_conn.get_candles("H1", backtest_candles // 2, offset=tf_offset("H1"))
    m15 = mt5_conn.get_candles("M15", backtest_candles, offset=tf_offset("M15"))
    m5 = mt5_conn.get_candles("M5", backtest_candles, offset=tf_offset("M5"))
    m1 = mt5_conn.get_candles("M1", backtest_candles + LOOKAHEAD_BARS, offset=offset_bars)

    mt5_conn.disconnect()
    print(f"✅ Đã tải xong: {len(m1)} nến M1, {len(m5)} nến M5, {len(m15)} nến M15, "
          f"{len(h1)} nến H1, {len(h4)} nến H4")
    if len(m1) > 0:
        print(f"   Giai đoạn test: {m1['time'].min()} → {m1['time'].max()}\n")
    else:
        print()

    results = []
    print("🔄 Đang chạy mô phỏng qua từng thời điểm trong quá khứ...")
    print("   (có thể mất vài phút tùy số lượng nến)\n")

    # Duyệt qua từng nến M1 trong quá khứ, giả lập "nếu lúc đó bot đang chạy"
    step = 5  # kiểm tra mỗi 5 nến M1 một lần để giảm thời gian tính toán
    total_checks = 0

    for i in range(200, len(m1) - LOOKAHEAD_BARS, step):
        current_time = m1["time"].iloc[i]

        # Cắt dữ liệu để chỉ dùng thông tin "đã biết tại thời điểm đó" (tránh look-ahead bias)
        h4_slice = h4[h4["time"] <= current_time].tail(200)
        h1_slice = h1[h1["time"] <= current_time].tail(200)
        m15_slice = m15[m15["time"] <= current_time].tail(200)
        m5_slice = m5[m5["time"] <= current_time].tail(200)
        m1_slice = m1[m1["time"] <= current_time].tail(100)

        if len(h4_slice) < 20 or len(h1_slice) < 20 or len(m15_slice) < 20:
            continue

        total_checks += 1
        current_price = m1["close"].iloc[i]

        candles = {"H4": h4_slice, "H1": h1_slice, "M15": m15_slice,
                   "M5": m5_slice, "M1": m1_slice}

        try:
            analysis = analyze_confluence(candles, current_price)
            signal = build_signal(analysis, current_price, Config.MIN_CONFLUENCE_SCORE)
        except Exception:
            continue

        if signal:
            future = m1.iloc[i + 1: i + 1 + LOOKAHEAD_BARS].reset_index(drop=True)
            if len(future) == 0:
                continue
            outcome = simulate_trade(future, signal)
            results.append({
                "time": current_time,
                "direction": signal["direction"],
                "entry": signal["entry"],
                "sl": signal["sl"],
                "tp": signal["tp"],
                "score": signal["score"],
                "result": outcome["result"],
                "bars_to_result": outcome["bars_to_result"],
                # nối bằng " | " để giữ trong 1 cột CSV — dùng để soi sau này layer nào
                # (structure/OB-FVG/price action/M1 trigger) đóng góp vào từng lệnh thắng/thua,
                # thay vì phải suy ra từ code như lần phân tích này.
                "reasons": " | ".join(signal["reasons"]),
            })

    print(f"✅ Đã quét {total_checks} thời điểm, tìm thấy {len(results)} tín hiệu thô "
          f"(trước khi lọc trùng lặp)\n")

    deduped = dedupe_signals(results)
    print(f"🧹 Sau khi gộp các tín hiệu trùng lặp (cùng hướng, cách nhau < {DEDUP_MINUTES} phút): "
          f"{len(deduped)} setup thực sự độc lập\n")

    print_report(deduped)
    save_report(deduped, results)
    log_run_summary(deduped, offset_bars, m1)


def dedupe_signals(results: list) -> list:
    """
    Gộp các tín hiệu cùng hướng xuất hiện liên tiếp cách nhau dưới DEDUP_MINUTES phút
    thành 1 setup duy nhất (chỉ giữ tín hiệu đầu tiên của cụm) — tránh đếm 1 cơ hội
    nhiều lần chỉ vì bot quét lại nhiều lần trong lúc giá chưa đổi cấu trúc.
    """
    if not results:
        return []

    df = pd.DataFrame(results).sort_values("time").reset_index(drop=True)
    keep = [True] * len(df)
    last_kept_time = {"BUY": None, "SELL": None}

    for i, row in df.iterrows():
        direction = row["direction"]
        last_time = last_kept_time[direction]
        if last_time is not None:
            gap_minutes = (row["time"] - last_time).total_seconds() / 60
            if gap_minutes < DEDUP_MINUTES:
                keep[i] = False
                continue
        last_kept_time[direction] = row["time"]

    return df[keep].to_dict("records")


def wilson_confidence_interval(wins: int, decided: int, z: float = 1.96) -> tuple:
    """
    Khoảng tin cậy Wilson 95% cho win rate — cho biết con số win rate thực sự
    có thể dao động trong khoảng nào với cỡ mẫu hiện tại (mẫu càng nhỏ, khoảng
    càng rộng, tức số liệu càng ít đáng tin). Trả về (low_pct, high_pct).
    """
    if decided == 0:
        return (0.0, 0.0)
    p = wins / decided
    denom = 1 + z ** 2 / decided
    centre = p + z ** 2 / (2 * decided)
    adj = z * math.sqrt((p * (1 - p) + z ** 2 / (4 * decided)) / decided)
    low = (centre - adj) / denom
    high = (centre + adj) / denom
    return (max(0.0, low * 100), min(100.0, high * 100))


def _direction_stats(df: pd.DataFrame, direction: str) -> tuple:
    sub = df[df["direction"] == direction]
    wins = len(sub[sub["result"] == "WIN"])
    losses = len(sub[sub["result"] == "LOSS"])
    decided = wins + losses
    wr = (wins / decided * 100) if decided > 0 else None
    return len(sub), wins, losses, decided, wr


def print_report(results: list):
    print("=" * 60)
    print("📈 BÁO CÁO BACKTEST")
    print("=" * 60)

    if not results:
        print("Không có tín hiệu nào đủ điều kiện trong giai đoạn test.")
        print("→ Có thể MIN_CONFLUENCE_SCORE đang để quá cao, hoặc thị trường")
        print("  giai đoạn này không có nhiều setup rõ ràng. Thử giảm ngưỡng")
        print("  trong .env (vd MIN_CONFLUENCE_SCORE=2.5) rồi chạy lại.")
        return

    df = pd.DataFrame(results)
    df["time"] = pd.to_datetime(df["time"])
    total = len(df)
    wins = len(df[df["result"] == "WIN"])
    losses = len(df[df["result"] == "LOSS"])
    timeouts = len(df[df["result"] == "TIMEOUT"])

    decided = wins + losses
    win_rate = (wins / decided * 100) if decided > 0 else 0

    print(f"Tổng số tín hiệu:     {total}")
    print(f"  ✅ Thắng (chạm TP): {wins}")
    print(f"  ❌ Thua (chạm SL):  {losses}")
    print(f"  ⏳ Chưa ngã ngũ:    {timeouts} (giá chưa chạm SL/TP trong "
          f"{LOOKAHEAD_BARS} nến M1 tiếp theo)")
    print()
    print(f"📊 Win rate (trên số lệnh đã ngã ngũ): {win_rate:.1f}%")

    if decided > 0:
        ci_low, ci_high = wilson_confidence_interval(wins, decided)
        print(f"   Khoảng tin cậy 95% (với {decided} lệnh đã ngã ngũ): "
              f"{ci_low:.1f}% – {ci_high:.1f}%")
        if decided < MIN_DECIDED_FOR_CONFIDENCE:
            print(f"   ⚠️  Mẫu còn nhỏ ({decided} lệnh, khuyến nghị ≥ {MIN_DECIDED_FOR_CONFIDENCE}) "
                  f"— khoảng tin cậy còn khá rộng, ĐỪNG dùng riêng con số win rate này để")
            print("       quyết định vào tiền thật. Chạy thêm ở các đoạn lịch sử khác "
                  "(dùng --offset) để gộp thêm mẫu.")
    print()

    if decided > 0:
        # R:R mặc định trong chiến lược là 1:2 -> hoà vốn cần win rate ~33%
        breakeven_wr = 33.3
        if win_rate > breakeven_wr:
            edge = (win_rate - breakeven_wr)
            print(f"→ Với R:R 1:2, ngưỡng hoà vốn là {breakeven_wr:.1f}% win rate.")
            print(f"  Kết quả hiện tại CAO HƠN ngưỡng hoà vốn {edge:.1f} điểm % "
                  f"→ có edge dương trên dữ liệu test này.")
            ci_low, _ = wilson_confidence_interval(wins, decided)
            if ci_low <= breakeven_wr:
                print(f"  ⚠️  Nhưng đầu dưới của khoảng tin cậy 95% ({ci_low:.1f}%) đã "
                      f"chạm dưới ngưỡng hoà vốn — với cỡ mẫu hiện tại, chưa thể loại trừ")
                print("      khả năng chiến lược thực ra chỉ hoà vốn hoặc lỗ nhẹ.")
        else:
            print(f"→ Với R:R 1:2, ngưỡng hoà vốn là {breakeven_wr:.1f}% win rate.")
            print(f"  Kết quả hiện tại THẤP HƠN ngưỡng hoà vốn → chưa có edge, "
                  f"cần điều chỉnh chiến lược trước khi tin tưởng.")

    # --- Tách riêng theo hướng lệnh: gộp chung BUY+SELL có thể che mất việc
    # 1 hướng đang gánh hết kết quả trong khi hướng kia gần như chưa được test ---
    print()
    print("Theo hướng lệnh:")
    for direction in ("BUY", "SELL"):
        n, w, l, dec, wr = _direction_stats(df, direction)
        if n == 0:
            print(f"  {direction}: không có tín hiệu nào")
            continue
        wr_str = f"{wr:.1f}%" if wr is not None else "N/A"
        note = ""
        if dec < 20:
            note = "  ⚠️ mẫu quá nhỏ để đánh giá riêng hướng này"
        print(f"  {direction}: {n} tín hiệu, {w} thắng / {l} thua ({dec} đã ngã ngũ), "
              f"win rate {wr_str}{note}")

    # --- Thống kê theo tuần: nếu win rate chỉ tốt ở 1-2 tuần rồi tệ ở các tuần khác,
    # nghĩa là kết quả tổng có thể chỉ phản ánh 1 đợt thị trường thuận lợi, không ổn định ---
    print()
    print("Theo tuần (kiểm tra tính ổn định qua thời gian):")
    df["week"] = df["time"].dt.to_period("W").apply(lambda p: p.start_time.strftime("%Y-%m-%d"))
    weekly_rows = []
    for week, group in df.groupby("week"):
        w = len(group[group["result"] == "WIN"])
        l = len(group[group["result"] == "LOSS"])
        dec = w + l
        wr = f"{(w / dec * 100):.0f}%" if dec > 0 else "N/A"
        weekly_rows.append((week, len(group), w, l, wr))
    for week, n, w, l, wr in weekly_rows:
        print(f"  Tuần bắt đầu {week}: {n} tín hiệu, {w}W/{l}L, win rate {wr}")

    print()
    print("Theo điểm hợp lưu (score):")
    print(df.groupby("score")["result"].value_counts().unstack(fill_value=0))
    print("=" * 60)


def save_report(deduped: list, raw: list = None):
    if not deduped:
        return
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    df = pd.DataFrame(deduped)
    filename = f"backtest_report_{timestamp}.csv"
    df.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"\n💾 Đã lưu {len(deduped)} setup đã gộp (dùng để tính win rate) vào: {filename}")

    if raw:
        raw_filename = f"backtest_report_{timestamp}_raw.csv"
        pd.DataFrame(raw).to_csv(raw_filename, index=False, encoding="utf-8-sig")
        print(f"💾 Đã lưu {len(raw)} tín hiệu thô (trước khi gộp trùng lặp) vào: {raw_filename}")

    print("   (mở bằng Excel để xem — encoding utf-8-sig đọc tiếng Việt không lỗi)")


def log_run_summary(deduped: list, offset_bars: int, m1: pd.DataFrame):
    """
    Ghi thêm 1 dòng tóm tắt của lần chạy này vào backtest_runs_log.csv (tạo file
    nếu chưa có, luôn append chứ không ghi đè). Mục đích: sau vài lần chạy với
    --offset khác nhau, mở file này ra là thấy ngay win rate có ổn định qua
    nhiều giai đoạn thị trường hay không — đây là căn cứ đáng tin hơn nhiều so
    với chỉ nhìn 1 lần chạy duy nhất.
    """
    df = pd.DataFrame(deduped) if deduped else pd.DataFrame(columns=["direction", "result"])

    total = len(df)
    wins = len(df[df["result"] == "WIN"]) if total else 0
    losses = len(df[df["result"] == "LOSS"]) if total else 0
    timeouts = len(df[df["result"] == "TIMEOUT"]) if total else 0
    decided = wins + losses
    win_rate = round(wins / decided * 100, 1) if decided > 0 else None
    ci_low, ci_high = wilson_confidence_interval(wins, decided) if decided > 0 else (None, None)

    _, buy_w, buy_l, buy_dec, buy_wr = _direction_stats(df, "BUY") if total else (0, 0, 0, 0, None)
    _, sell_w, sell_l, sell_dec, sell_wr = _direction_stats(df, "SELL") if total else (0, 0, 0, 0, None)

    row = {
        "run_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "offset_bars": offset_bars,
        "period_start": m1["time"].min() if len(m1) else None,
        "period_end": m1["time"].max() if len(m1) else None,
        "min_confluence_score": Config.MIN_CONFLUENCE_SCORE,
        "total_setups": total,
        "wins": wins,
        "losses": losses,
        "timeouts": timeouts,
        "decided": decided,
        "win_rate_pct": win_rate,
        "ci95_low": round(ci_low, 1) if ci_low is not None else None,
        "ci95_high": round(ci_high, 1) if ci_high is not None else None,
        "buy_decided": buy_dec,
        "buy_win_rate_pct": round(buy_wr, 1) if buy_wr is not None else None,
        "sell_decided": sell_dec,
        "sell_win_rate_pct": round(sell_wr, 1) if sell_wr is not None else None,
    }

    log_df = pd.DataFrame([row])
    file_exists = os.path.isfile(RUN_LOG_FILE)
    log_df.to_csv(RUN_LOG_FILE, mode="a", header=not file_exists, index=False,
                   encoding="utf-8-sig")

    print(f"\n📝 Đã ghi tóm tắt lần chạy này vào {RUN_LOG_FILE} "
          f"(mở file này để so sánh win rate qua các lần chạy/giai đoạn khác nhau)")

    # Đọc lại toàn bộ log để nhắc tổng số mẫu đã gom được qua tất cả các lần chạy
    try:
        all_runs = pd.read_csv(RUN_LOG_FILE)
        total_decided_all_runs = all_runs["decided"].fillna(0).sum()
        print(f"   Tổng cộng đến giờ: {len(all_runs)} lần chạy, "
              f"{int(total_decided_all_runs)} lệnh đã ngã ngũ gộp lại.")
        if total_decided_all_runs < MIN_DECIDED_FOR_CONFIDENCE:
            print(f"   → Vẫn dưới ngưỡng khuyến nghị ({MIN_DECIDED_FOR_CONFIDENCE} lệnh) để "
                  f"tự tin vào tiền thật. Chạy thêm với --offset khác.")
        else:
            print(f"   → Đã đủ ngưỡng khuyến nghị ({MIN_DECIDED_FOR_CONFIDENCE} lệnh). "
                  f"Vẫn nên xem win rate có đồng đều giữa các lần chạy không, không chỉ nhìn tổng.")
    except Exception:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest chiến lược confluence trên dữ liệu MT5")
    parser.add_argument("--offset", type=int, default=0,
                         help="Số nến M1 lùi lại trước khi bắt đầu lấy dữ liệu test "
                              "(0 = đoạn gần nhất hiện tại). Dùng để test các đoạn lịch sử "
                              "khác nhau, không lặp lại đoạn đã test.")
    parser.add_argument("--candles", type=int, default=BACKTEST_CANDLES,
                         help=f"Số nến M1 dùng để test (mặc định {BACKTEST_CANDLES})")
    args = parser.parse_args()

    run_backtest(offset_bars=args.offset, backtest_candles=args.candles)