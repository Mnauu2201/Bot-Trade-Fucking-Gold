## � Cập nhật nhật ký — 2026-08-26

### Chuyển sang broker demo thật (Exness)

- MetaQuotes-Demo không đủ lịch sử M1 để backtest các offset xa (vd --offset 106400 trở đi)
  → chuyển sang demo thật: Exness, server `Exness-MT5Trial6`, account `414250367`
- Symbol vàng trên Exness có hậu tố "m": `XAUUSDm`, không phải `XAUUSD` — đã sửa trong `.env`

### Batch backtest 12 tháng dữ liệu (offset 106400 → 456000)

Dùng script mới `run_batch_backtest.py` (tự động lặp offset, tự dừng khi đủ mẫu),
kết quả gộp 24 lần chạy, tổng **215 tín hiệu**, lọc riêng **score >= 3.5**:

| Ngưỡng                   | Số lệnh đã ngã ngũ | Thắng | Win rate | CI 95%        |
| ------------------------ | ------------------ | ----- | -------- | ------------- |
| score >= 3.5 (đang dùng) | 105                | 63    | 60.0%    | 50.4% – 68.9% |
| score == 4.0 riêng       | 45                 | 30    | 66.7%    | 52.1% – 78.6% |

→ Cận dưới CI (50.4%) đã cao hơn hẳn ngưỡng hoà vốn 33.3% (R:R 1:2) — có edge thật,
đáng tin hơn nhiều so với mẫu 16 lệnh lần trước.

### Phân tích theo layer (score >= 3.5, n=105)

- **Structure H4+H1 đồng thuận** đáng tin hơn chỉ có H1 xác nhận riêng:
  - H4+H1 đồng thuận / CHoCH: 72.7% (n=22)
  - H4+H1 đồng thuận / BOS: 60.9% (n=23)
  - Chỉ H1 / BOS: 60.0% (n=15)
  - Chỉ H1 / CHoCH: 53.3% (n=45) — nhóm đông nhất nhưng yếu nhất
- **Order Block vs FVG**: OB 66.1% (n=59) >> FVG 52.2% (n=46, gần coinflip)
- **M1 trigger (BOS vs CHoCH)**: gần như không khác biệt (58.5% vs 60.9%)
- **Price action pattern**: chênh lệch rất lớn
  - Mạnh: bearish_pin_bar 85.7% (n=7), bullish_rejection 71.9% (n=32), bearish_rejection 71.4% (n=14)
  - Yếu: bullish_engulfing 30.0% (n=10), bullish_pin_bar 38.5% (n=13)

### Đã sửa `strategy/confluence.py` theo phát hiện trên

- Layer 2 (OB/FVG): FVG giờ +0.5 thay vì +1 (OB vẫn +1)
- Layer 3 (Price action): pattern có "rejection" vẫn +1; engulfing/pin_bar đứng riêng lẻ chỉ +0.5

### Kiểm chứng out-of-sample bản confluence.py đã sửa

Chạy `run_batch_backtest.py` trên offset 471200 → 699200 (dữ liệu mới hoàn toàn, ~8 tháng,
2024-08 → 2025-04, chưa từng dùng để tìm trọng số):

|                                | n   | Win rate | CI 95%        |
| ------------------------------ | --- | -------- | ------------- |
| Dữ liệu cũ (dùng tìm trọng số) | 105 | 60.0%    | 50.4% – 68.9% |
| Dữ liệu mới (out-of-sample)    | 50  | 66.0%    | 52.2% – 77.6% |

→ Win rate **không sụt** trên dữ liệu mới (thậm chí tăng nhẹ) — thay đổi trọng số
không bị overfit vào nhiễu của mẫu cũ, có thể tin dùng.

### Phát hiện vấn đề TIMEOUT (bias của cửa sổ đo lường)

Ở ngưỡng score>=3.5, tỷ lệ tín hiệu bị TIMEOUT (không chạm SL/TP trong 200 nến M1
~3.3 giờ) lên tới **51.4%** trên tổng 219 tín hiệu đã test. Kiểm tra kỹ thấy:

- Lệnh TIMEOUT có TP/SL cách entry trung bình ~60$/oz — gấp 3-4 lần lệnh đã ngã ngũ (~16-20$/oz)
- → Setup mục tiêu xa (thường dựa cấu trúc H4/H1 lớn) cần nhiều thời gian hơn 200 phút mới
  đi tới đích, bị cắt ngang oan trước khi biết kết quả thật — làm méo win rate tính được

**Đã sửa `backtest.py`:** `LOOKAHEAD_BARS` từ 200 → 800 (~13.3 giờ) để giảm bias này.

### Kiểm chứng lại với LOOKAHEAD_BARS=800 (2 đợt chạy, offset 714400 → 1276800)

Dữ liệu hoàn toàn mới, phủ 2022-12 → 2024-08 (~20 tháng), tổng 38 lần chạy, gộp lại:

|                                   | n       | Win rate  | CI 95%            | Timeout rate |
| --------------------------------- | ------- | --------- | ----------------- | ------------ |
| Đợt 1 (714400→881600, n nhỏ)      | 50      | 58.0%     | 44.2% – 70.6%     | 33.3%        |
| **Gộp cả 2 đợt (714400→1276800)** | **151** | **62.3%** | **54.3% – 69.6%** | **33.2%**    |

Theo hướng lệnh (gộp cả 2 đợt): BUY 60.4% (n=96), SELL 65.5% (n=55) — cả hai hướng đều tốt,
không lệch bất thường.

→ **Đây là con số đáng tin cậy nhất tính đến thời điểm này**: mẫu đủ lớn (151 lệnh),
cửa sổ đo lường không còn bias (timeout ổn định ~33%), nhất quán qua ~20 tháng dữ liệu
đa dạng, cận dưới CI (54.3%) cách xa ngưỡng hoà vốn 33.3%.

### Việc cần làm tiếp theo

- [x] ~~Kiểm chứng out-of-sample bản confluence.py đã sửa~~ → đã xong, không overfit
- [x] ~~Sửa bias TIMEOUT (LOOKAHEAD_BARS 200→800) và kiểm chứng lại~~ → đã xong,
      win rate ổn định quanh 62.3% với mẫu lớn
- [ ] Có thể coi Phase 1 đã đủ số liệu tin cậy để cân nhắc chuyển tiếp — xem đánh giá
      trao đổi riêng về thời điểm chuyển Phase 1.5 (crawl tin tức + sentiment)
- [ ] Đánh giá xem có nên thêm EMA/RSI/MACD trend filter và/hoặc vùng Fibonacci retracement
      làm layer bổ sung hay không — tài liệu người dùng tự tổng hợp (2026-08-26), đánh giá:
      nên hoãn, các concept này trùng lặp về mặt ý tưởng với structure H4/H1 và OB/FVG hiện
      có, nên thử nghiệm A/B riêng biệt sau, không trộn cùng lúc với các thay đổi khác
