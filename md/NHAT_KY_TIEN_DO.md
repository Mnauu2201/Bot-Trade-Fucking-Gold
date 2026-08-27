# 📒 Nhật ký tiến độ — Gold Analysis Bot

File này dùng để theo dõi những gì đã làm, thông tin đã cấu hình, và việc cần làm tiếp theo.
Cập nhật thủ công mỗi khi có thay đổi.

---

## ✅ Trạng thái hiện tại

**Phase 1 (Bot phân tích) — Đã chạy thành công lần đầu: 2026-08-25**

- MT5 kết nối OK
- Telegram bot kết nối OK
- Groq API kết nối OK
- Vòng lặp phân tích chạy đều, chưa có tín hiệu nào đạt ngưỡng (bình thường, đang chờ setup đẹp)

---

## 🔑 Thông tin đã cấu hình (tham khảo — không chia sẻ file này)

### MT5

| Trường          | Giá trị                       |
| --------------- | ----------------------------- |
| Login           | `10012363128`                 |
| Server          | `MetaQuotes-Demo`             |
| Loại tài khoản  | Demo, Hedge, Forex Hedged USD |
| Balance ban đầu | 5,000,000 USD (demo ảo)       |
| Leverage        | 1:100                         |
| Symbol theo dõi | XAUUSD                        |

_(Lưu ý: có 2 tài khoản demo trong Navigator — `5054935495` là cái cũ đã hết hạn/không login được,
tài khoản đang dùng thực tế là `10012363128`.)_

### Telegram

- Bot đã tạo qua BotFather, token lưu trong `.env`
- Chat ID: `1828511873`

### Groq

- Model đang dùng: `llama-3.3-70b-versatile`
- Key lấy từ 1 trong số các tài khoản Groq cá nhân đã có sẵn

### Bot behavior

- Quét giá mỗi 60 giây
- Ngưỡng gửi tín hiệu: điểm hợp lưu ≥ 3.5/4 (nâng từ 3.0 ngày 2026-08-25, xem phần
  "Phân tích ngưỡng điểm" bên dưới)

---

## 📌 Việc cần làm tiếp theo

- [x] ~~Tự đối chiếu tín hiệu thủ công~~ → **đã tự động hoá bằng `backtest.py`**, không cần tự
      tính tay hay hiểu sâu về trading — script tự đọc dữ liệu lịch sử và tự chấm thắng/thua
- [x] Chạy `backtest.py` qua 7 giai đoạn khác nhau (offset 0 → 91200) → có baseline gộp
- [x] Dựa vào kết quả backtest, quyết định chỉnh `MIN_CONFLUENCE_SCORE` → **đã nâng 3.0 → 3.5**
      (xem "Phân tích ngưỡng điểm" bên dưới)
- [ ] Chạy lại `backtest.py` ở nhiều offset với ngưỡng 3.5 mới để xác nhận win rate thực tế
      (mẫu hiện tại ở score 3.5 mới có 16 lệnh — cần ≥ 50 để tin cậy)
- [ ] Dùng cột `reasons` mới thêm vào CSV để soi layer nào (structure/OB-FVG/price action/
      M1 trigger) đóng góp nhiều nhất vào các lệnh thắng, layer nào hay "ăn theo" mà không
      thêm giá trị
- [ ] Module crawl tin tức vĩ mô/dầu + Groq sentiment (chưa bắt đầu — để sau khi có baseline)
- [ ] Phase 2: tự động đặt lệnh (chỉ làm sau khi Phase 1 có số liệu tin cậy)

---

## 🔍 Phân tích ngưỡng điểm hợp lưu (2026-08-25)

**Bối cảnh:** đã có `bt_buy_sell.zip` chứa 7 lần chạy `backtest.py` với `--offset` khác nhau,
phủ giai đoạn 2026-05-11 → 2026-08-25 (~3.5 tháng, không chồng lấn giữa các đoạn).

**Kết quả gộp cả 7 lần chạy (167 lệnh đã ngã ngũ):**

|             | Số lệnh | Thắng | Thua | Win rate | CI 95%        |
| ----------- | ------- | ----- | ---- | -------- | ------------- |
| Gộp toàn bộ | 167     | 93    | 74   | 55.7%    | 48.1% – 63.0% |

→ Cao hơn ngưỡng hoà vốn (33.3% ở R:R 1:2) rõ rệt, và mẫu đã đủ lớn (167 > 50) để tin số
này hơn bất kỳ 1 lần chạy đơn lẻ nào (ví dụ lần chạy gần nhất chỉ 8 lệnh, win rate 75% —
không đại diện).

**Phân tích theo điểm hợp lưu (score), gộp cả 7 lần chạy:**

| Score | Tổng tín hiệu | Đã ngã ngũ | Win rate                    |
| ----- | ------------- | ---------- | --------------------------- |
| 3.0   | 166           | 145        | 54.5%                       |
| 3.5   | 31            | 16         | 75.0%                       |
| 4.0   | 7             | 6          | 33.3% (mẫu quá nhỏ, bỏ qua) |

**Phát hiện:** ~81% tín hiệu (166/204) chỉ đạt đúng điểm sàn 3.0 — tức bot gần như luôn bắn
tín hiệu ngay khi vừa chạm ngưỡng lọc, hiếm khi tích luỹ đủ điểm cao hơn. Đọc code
`strategy/confluence.py` thì thấy nguyên nhân: layer 4 (M1 trigger, +1 điểm) đòi hỏi một
BOS/CHoCH _mới ngay lúc đó_ trên khung M1, phải trùng thời điểm với 3 layer kia (structure
H4/H1, OB/FVG, price action M15/M5) — điều kiện hiếm khi xảy ra đồng thời. Vì vậy phần lớn
setup dừng ở 3.0 (đủ 3 layer đầu, thiếu trigger M1), chỉ 15% đạt 3.5+.

Win rate ở 3.0 (54.5%, n=145) gần với coinflip, trong khi 3.5 (75.0%, n=16) cho thấy edge rõ
rệt hơn hẳn — dù mẫu 16 lệnh vẫn còn nhỏ để khẳng định chắc chắn.

**Đã triển khai:**

1. `config.py`: `MIN_CONFLUENCE_SCORE` đổi từ `int()` sang `float()` — bug trước đó khiến nếu
   ai đặt `MIN_CONFLUENCE_SCORE=3.5` trong `.env` thì bị ép về `3`, ngưỡng lọc không có tác
   dụng thật. Đồng thời đổi giá trị mặc định từ `3` → `3.5`.
2. `backtest.py`: thêm cột `reasons` vào cả 2 file CSV export (report đã gộp + report thô) —
   nối các lý do từ `analysis["reasons"]` bằng `" | "`. Mục đích: lần phân tích sau có thể
   soi trực tiếp layer nào góp mặt trong từng lệnh thắng/thua từ CSV, thay vì phải đọc lại
   code để suy luận như lần này.

**Việc cần làm tiếp:** chạy lại `backtest.py --offset ...` qua các giai đoạn cũ với ngưỡng
3.5 mới để có mẫu ≥ 50 lệnh ở đúng ngưỡng sẽ dùng thật — con số 75% hiện tại (n=16) mới chỉ
là tín hiệu định hướng, chưa đủ để quyết định vào tiền thật.

---

## 🧪 Cách chạy Backtest

File `backtest.py` tự động quét dữ liệu lịch sử MT5, giả lập "nếu bot chạy lúc đó thì tín hiệu
nào được gửi", rồi tự kiểm tra giá chạm SL hay TP trước — ra thẳng con số win rate.
**Bạn không cần tự đọc chart hay tự đánh giá gì cả**, chỉ cần đọc báo cáo cuối:

```powershell
cd C:\gold-bot
venv\Scripts\activate
python backtest.py
```

Chạy xong sẽ thấy:

- Tổng số tín hiệu tìm được trong dữ liệu lịch sử
- Số thắng / thua / chưa ngã ngũ
- Win rate (%)
- So sánh với ngưỡng hoà vốn (~33% với R:R 1:2 hiện tại) — script tự nói cho bạn biết
  chiến lược đang có lời hay không trên dữ liệu test, không cần bạn tự tính
- 1 file `.csv` lưu chi tiết từng lệnh (mở bằng Excel xem lại được)

Nếu báo "Không có tín hiệu nào" → thử hạ `MIN_CONFLUENCE_SCORE` trong `.env` xuống `2.5`
rồi chạy lại `backtest.py` (không cần chạy lại `main.py`).

---

## 🐛 Lỗi đã gặp & cách xử lý (để tra cứu lại nếu lặp lại)

| Lỗi                                                           | Nguyên nhân                                              | Cách sửa                                                                                            |
| ------------------------------------------------------------- | -------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `groq.../TypeError: unexpected keyword argument 'proxies'`    | Xung đột phiên bản `httpx` mới với Groq SDK cũ           | `pip install "httpx==0.27.2"`                                                                       |
| `MT5 ConnectionError: Authorization failed (Invalid account)` | Tài khoản demo cũ (`5054935495`) hết hạn/sai mật khẩu    | Tạo tài khoản demo mới qua File → Open an Account                                                   |
| `telegram.error.InvalidToken`                                 | Dán nhầm Groq key (`gsk_...`) vào ô `TELEGRAM_BOT_TOKEN` | Lấy đúng token dạng `số:chuỗi` từ BotFather, Groq key riêng dạng `gsk_...` để đúng ô `GROQ_API_KEY` |

---

## 📝 Log nhật ký theo ngày

### 2026-08-25

- Setup xong toàn bộ môi trường, kết nối MT5 + Telegram + Groq thành công
- Bot chạy vòng lặp ổn định, chưa ghi nhận tín hiệu nào đạt ngưỡng 3/4
- Chạy `backtest.py` qua 7 giai đoạn (offset 0-91200, ~3.5 tháng dữ liệu): win rate gộp
  55.7% trên 167 lệnh (CI 48.1-63.0%) — có edge dương so với ngưỡng hoà vốn 33.3%
- Phân tích theo score: 81% tín hiệu chỉ đạt sàn 3.0 (win rate 54.5%), trong khi 3.5 đạt
  75.0% nhưng mẫu còn nhỏ (16 lệnh). Xem chi tiết ở mục "Phân tích ngưỡng điểm hợp lưu" ở trên.
- Sửa `config.py`: `MIN_CONFLUENCE_SCORE` từ `int()` → `float()`, mặc định 3.0 → 3.5
- Sửa `backtest.py`: thêm cột `reasons` vào CSV export để phân tích layer sau này dễ hơn
- Tiếp theo: chạy lại backtest với ngưỡng 3.5 qua nhiều offset để có mẫu đủ lớn trước khi
  cân nhắc Phase 2 (tự động đặt lệnh)
