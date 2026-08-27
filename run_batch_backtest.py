"""
run_batch_backtest.py — Tự động chạy backtest.py qua nhiều đoạn lịch sử (offset)
liên tiếp, không cần gõ tay từng lệnh, và tự dừng khi đã đủ mẫu ở ngưỡng
MIN_CONFLUENCE_SCORE hiện tại (mặc định cần ≥ 50 lệnh đã ngã ngũ ở score >= 3.5).

Cách chạy:
    python run_batch_backtest.py
    python run_batch_backtest.py --start 106400 --step 15200 --target 50 --max-runs 15

Mỗi lần lặp gọi thẳng hàm run_backtest() trong backtest.py (không dùng subprocess),
nên vẫn ghi CSV + backtest_runs_log.csv y hệt như chạy tay từng lệnh.

Sau mỗi vòng, script tự đọc lại các file backtest_report_*.csv (không phải _raw)
vừa tạo trong thư mục hiện tại, lọc dòng score >= 3.5, và cộng dồn số lệnh đã
ngã ngũ (WIN/LOSS) để biết khi nào đủ mẫu thì dừng.
"""

import argparse
import glob
import os
import sys
import time

import pandas as pd

from backtest import run_backtest
from config import Config

SCORE_THRESHOLD = 3.5  # ngưỡng score đang thực sự dùng để tính mẫu tin cậy


def count_decided_at_threshold(score_threshold: float = SCORE_THRESHOLD) -> int:
    """Đọc lại toàn bộ backtest_report_*.csv (bỏ qua *_raw.csv) đã có trong thư mục,
    lọc score >= threshold, đếm số lệnh đã ngã ngũ (WIN hoặc LOSS, bỏ TIMEOUT)."""
    files = [f for f in glob.glob("backtest_report_*.csv") if not f.endswith("_raw.csv")]
    if not files:
        return 0

    total_decided = 0
    for f in files:
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        if "score" not in df.columns or "result" not in df.columns:
            continue
        sub = df[df["score"] >= score_threshold]
        total_decided += len(sub[sub["result"].isin(["WIN", "LOSS"])])
    return total_decided


def main():
    parser = argparse.ArgumentParser(
        description="Chạy backtest.py lặp qua nhiều offset cho đến khi đủ mẫu ở score cao"
    )
    parser.add_argument("--start", type=int, default=0,
                         help="Offset bắt đầu (số nến M1 lùi lại). Mặc định 0.")
    parser.add_argument("--step", type=int, default=15200,
                         help="Mỗi vòng lùi thêm bao nhiêu nến M1 (mặc định 15200, "
                              "khớp với 1 đợt ~10 ngày giao dịch không trùng lặp).")
    parser.add_argument("--candles", type=int, default=15000,
                         help="Số nến M1 mỗi lần test (mặc định 15000, giống backtest.py).")
    parser.add_argument("--target", type=int, default=50,
                         help="Số lệnh đã ngã ngũ ở score >= %.1f cần đạt để dừng "
                              "(mặc định 50)." % SCORE_THRESHOLD)
    parser.add_argument("--max-runs", type=int, default=20,
                         help="Giới hạn an toàn: tối đa bao nhiêu vòng lặp (mặc định 20), "
                              "để tránh chạy vô hạn nếu lịch sử MT5 hết dữ liệu.")
    parser.add_argument("--score-threshold", type=float, default=SCORE_THRESHOLD,
                         help="Ngưỡng score dùng để đếm mẫu (mặc định %.1f, nên khớp với "
                              "Config.MIN_CONFLUENCE_SCORE đang dùng)." % SCORE_THRESHOLD)
    args = parser.parse_args()

    print(f"⚙️  MIN_CONFLUENCE_SCORE hiện tại trong config: {Config.MIN_CONFLUENCE_SCORE}")
    print(f"🎯 Mục tiêu: {args.target} lệnh đã ngã ngũ (WIN/LOSS) ở score >= {args.score_threshold}")
    print(f"🔁 Sẽ chạy tối đa {args.max_runs} vòng, mỗi vòng lùi thêm {args.step} nến M1\n")

    offset = args.start
    run_count = 0

    # Tính mẫu đã có sẵn từ các lần chạy trước đó (nếu CSV cũ còn nằm trong thư mục)
    decided_so_far = count_decided_at_threshold(args.score_threshold)
    print(f"📂 Mẫu đã có sẵn trong thư mục (từ các lần chạy trước): "
          f"{decided_so_far} lệnh ở score >= {args.score_threshold}\n")

    while decided_so_far < args.target and run_count < args.max_runs:
        run_count += 1
        print("=" * 70)
        print(f"▶️  Vòng {run_count}/{args.max_runs} — offset = {offset}")
        print("=" * 70)

        try:
            run_backtest(offset_bars=offset, backtest_candles=args.candles)
        except Exception as e:
            print(f"\n❌ Lỗi khi chạy offset={offset}: {e}")
            print("   Dừng batch tại đây — có thể lịch sử MT5 đã hết ở mốc này.")
            break

        decided_so_far = count_decided_at_threshold(args.score_threshold)
        print(f"\n📊 Tổng mẫu luỹ kế ở score >= {args.score_threshold}: "
              f"{decided_so_far}/{args.target}\n")

        offset += args.step
        # nghỉ ngắn giữa các vòng để không dồn dập gọi MT5 liên tục
        time.sleep(1)

    print("\n" + "=" * 70)
    if decided_so_far >= args.target:
        print(f"✅ HOÀN THÀNH: đã đạt {decided_so_far} lệnh ở score >= {args.score_threshold} "
              f"(mục tiêu {args.target}).")
        print(f"   Offset cuối cùng đã test: {offset - args.step} "
              f"(vòng kế tiếp sẽ là --offset {offset} nếu muốn test thêm).")
    else:
        print(f"⏸️  DỪNG do chạm giới hạn {args.max_runs} vòng hoặc hết dữ liệu lịch sử.")
        print(f"   Mới đạt {decided_so_far}/{args.target} lệnh ở score >= {args.score_threshold}.")
        print(f"   Nếu muốn chạy tiếp: python run_batch_backtest.py --start {offset} "
              f"--target {args.target - decided_so_far}")
    print("=" * 70)

    print(f"\n💡 Mở {os.path.abspath('backtest_runs_log.csv')} bằng Excel để xem toàn bộ "
          f"lịch sử các lần chạy, hoặc mở các file backtest_report_*.csv để soi từng lệnh "
          f"(cột 'reasons' cho biết layer nào góp mặt vào mỗi lệnh thắng/thua).")


if __name__ == "__main__":
    main()
