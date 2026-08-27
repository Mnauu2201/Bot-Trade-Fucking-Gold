# 🥇 Gold Analysis Bot — Hướng dẫn Setup từ A-Z

Bot phân tích thị trường XAUUSD (vàng), chạy 24/7 trên Windows, tự tìm entry theo mô hình
hợp lưu đa khung thời gian (Multi-Timeframe Confluence), gửi tín hiệu qua Telegram, và
trò chuyện tiếng Việt qua Groq API.

**Đây là bot phân tích (Phase 1)** — chỉ gửi tín hiệu, KHÔNG tự đặt lệnh. Việc vào lệnh do
bạn quyết định trên MT5.

---

## 📋 Mục lục

1. [Yêu cầu hệ thống](#1-yêu-cầu-hệ-thống)
2. [Cài đặt Python & môi trường](#2-cài-đặt-python--môi-trường)
3. [Cài đặt MetaTrader 5](#3-cài-đặt-metatrader-5)
4. [Tạo Telegram Bot](#4-tạo-telegram-bot)
5. [Cấu hình Groq API](#5-cấu-hình-groq-api)
6. [Cấu trúc dự án](#6-cấu-trúc-dự-án)
7. [File cấu hình `.env`](#7-file-cấu-hình-env)
8. [Chạy thử bot](#8-chạy-thử-bot)
9. [Chạy 24/7 trên Windows](#9-chạy-247-trên-windows)
10. [Chiến lược phân tích (Confluence Scoring)](#10-chiến-lược-phân-tích-confluence-scoring)
11. [Định hướng Phase 2 — Auto Trade](#11-định-hướng-phase-2--auto-trade)

---

## 1. Yêu cầu hệ thống

| Thành phần   | Yêu cầu                                                                       |
| ------------ | ----------------------------------------------------------------------------- |
| Hệ điều hành | Windows 10/11 (bắt buộc — gói `MetaTrader5` của Python chỉ chạy trên Windows) |
| Python       | 3.10 hoặc 3.11 (khuyến nghị, tránh 3.12+ vì một số gói chưa hỗ trợ đầy đủ)    |
| MetaTrader 5 | Bản Desktop (không phải bản Store), đã đăng nhập tài khoản Demo               |
| RAM          | Tối thiểu 4GB trống cho việc chạy nền liên tục                                |
| Kết nối mạng | Ổn định, laptop không được sleep khi đóng nắp (xem mục 9)                     |

---

## 2. Cài đặt Python & môi trường

### Bước 2.1 — Cài Python

Tải Python 3.11 tại: https://www.python.org/downloads/

⚠️ Khi cài, **tick chọn "Add Python to PATH"** ở màn hình đầu tiên của installer.

Kiểm tra sau khi cài xong (mở Command Prompt / PowerShell):

```powershell
python --version
```

### Bước 2.2 — Tạo thư mục dự án & môi trường ảo

```powershell
mkdir C:\gold-bot
cd C:\gold-bot
python -m venv venv
venv\Scripts\activate
```

Sau khi activate, đầu dòng lệnh sẽ hiện `(venv)`.

### Bước 2.3 — Cài các thư viện cần thiết

Copy toàn bộ nội dung file `requirements.txt` (đính kèm bên dưới) vào `C:\gold-bot\requirements.txt`,
rồi chạy:

```powershell
pip install -r requirements.txt
```

---

## 3. Cài đặt MetaTrader 5

1. Tải MT5 bản Desktop từ broker bạn đang dùng (từ ảnh bạn gửi, tài khoản Demo hiện tại là
   server **MetaQuotes-Demo**, login `5054935495` — đây là demo mẫu của MetaQuotes, bạn có thể
   dùng để test, nhưng khi triển khai thật nên dùng demo của đúng broker bạn định trade thật).
2. Mở MT5 → **File → Login to Trade Account** → nhập lại Login/Password/Server.
3. Vào **Tools → Options → Expert Advisors** → tick:
   - ✅ Allow automated trading
   - ✅ Allow DLL imports
4. **Quan trọng:** để bot Python lấy được dữ liệu, MT5 terminal phải đang **mở và đăng nhập**
   trong lúc bot chạy (chạy nền cũng được, không cần focus cửa sổ).

---

## 4. Tạo Telegram Bot

1. Mở Telegram, tìm **@BotFather**.
2. Gửi lệnh `/newbot`, đặt tên bot (vd: `Gold Analysis Bot`), đặt username (phải kết thúc bằng
   `bot`, vd: `mygoldanalysis_bot`).
3. BotFather trả về một **token** dạng: `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   → Lưu lại, đây là `TELEGRAM_BOT_TOKEN`.
4. Lấy **Chat ID** của bạn:
   - Nhắn bất kỳ tin nào cho bot vừa tạo.
   - Mở trình duyệt, truy cập:
     `https://api.telegram.org/bot<TOKEN>/getUpdates`
     (thay `<TOKEN>` bằng token ở bước 3)
   - Tìm trường `"chat":{"id": ...}` → đó là `TELEGRAM_CHAT_ID`.

---

## 5. Cấu hình Groq API

Bạn đã có sẵn key rồi, chỉ cần chọn 1 key để dùng cho bot này và điền vào `.env` (mục 7).

Model khuyến nghị dùng cho chat tiếng Việt + phân tích nhanh: `llama-3.3-70b-versatile`
(cân bằng tốc độ/chất lượng). Nếu cần nhanh hơn cho việc xử lý liên tục, có thể dùng
`llama-3.1-8b-instant`.

---

## 6. Cấu trúc dự án

```
gold-bot/
├── .env                      # Cấu hình bí mật (không chia sẻ file này)
├── requirements.txt
├── config.py                 # Đọc cấu hình từ .env
├── mt5_connector.py           # Kết nối MT5, lấy dữ liệu giá
├── strategy/
│   ├── __init__.py
│   ├── structure.py           # Phát hiện BOS/CHoCH, Order Block, FVG
│   ├── price_action.py        # Nhận diện mô hình nến
│   └── confluence.py          # Chấm điểm hợp lưu, ra quyết định
├── telegram_bot.py             # Gửi tín hiệu + chat 2 chiều qua Groq
├── groq_client.py               # Wrapper gọi Groq API
└── main.py                       # Vòng lặp chính, chạy 24/7
```

---

## 7. File cấu hình `.env`

Tạo file `.env` trong `C:\gold-bot\`, điền các giá trị của bạn:

```env
# --- MT5 ---
MT5_LOGIN=5054935495
MT5_PASSWORD=dien_password_that_cua_ban
MT5_SERVER=MetaQuotes-Demo
MT5_SYMBOL=XAUUSD

# --- Telegram ---
TELEGRAM_BOT_TOKEN=dien_token_tu_botfather
TELEGRAM_CHAT_ID=dien_chat_id_cua_ban

# --- Groq ---
GROQ_API_KEY=dien_1_trong_so_groq_key_cua_ban
GROQ_MODEL=llama-3.3-70b-versatile

# --- Bot behavior ---
CHECK_INTERVAL_SECONDS=60
MIN_CONFLUENCE_SCORE=3
```

⚠️ **Không upload file `.env` lên GitHub hay chia sẻ cho ai** — nó chứa mật khẩu MT5 và token.

---

## 8. Chạy thử bot

```powershell
cd C:\gold-bot
venv\Scripts\activate
python main.py
```

Nếu mọi thứ đúng, bạn sẽ thấy log kết nối MT5 thành công, và nhận được tin nhắn Telegram
"🟢 Bot đã khởi động" trong vài giây.

Bot sẽ:

- Quét giá mỗi `CHECK_INTERVAL_SECONDS` giây (mặc định 60s)
- Phân tích cấu trúc thị trường trên H4/H1/M15/M5
- Khi điểm hợp lưu ≥ `MIN_CONFLUENCE_SCORE`, gửi tín hiệu chi tiết qua Telegram
- Bạn có thể nhắn trực tiếp cho bot Telegram để hỏi bằng tiếng Việt (vd: "vàng đang xu hướng gì?")

---

## 9. Chạy 24/7 trên Windows

Để laptop chạy bot liên tục không bị ngắt:

1. **Tắt Sleep:** Settings → System → Power & sleep → "Screen and sleep" → **Never**
   (khi cắm sạc).
2. **Không đóng nắp laptop** hoặc vào Control Panel → Power Options → Chọn "Do nothing"
   khi đóng nắp.
3. **Tự động khởi động lại bot nếu Windows restart** (khuyến nghị dùng Task Scheduler):
   - Mở **Task Scheduler** → Create Task
   - Trigger: "At log on"
   - Action: chạy `C:\gold-bot\venv\Scripts\python.exe C:\gold-bot\main.py`
   - Tick "Run whether user is logged on or not"

---

## 10. Chiến lược phân tích (Confluence Scoring)

Bot chấm điểm mỗi cơ hội theo 4 lớp, cộng điểm khi đồng thuận:

| Lớp                       | Kiểm tra                                                    | Điểm |
| ------------------------- | ----------------------------------------------------------- | ---- |
| **Structure (H4/H1)**     | Có BOS/CHoCH đúng hướng gần đây không                       | +1   |
| **Order Block / FVG**     | Giá đang test lại vùng OB hoặc Fair Value Gap chưa lấp      | +1   |
| **Price Action (M15/M5)** | Có nến xác nhận (engulfing, pin bar, rejection) tại vùng đó | +1   |
| **Trigger (M1)**          | Break of structure nhỏ xác nhận hướng vào lệnh              | +1   |

→ Tín hiệu chỉ được gửi khi tổng điểm ≥ `MIN_CONFLUENCE_SCORE` (mặc định 3/4).
Điểm càng cao, độ tin cậy thống kê càng cao — đây là cách xây "entry đẹp" có căn cứ,
khác với việc vẽ lại chart sau khi biết kết quả.

_(Module tin tức vĩ mô/dầu mỏ để lọc thêm risk-on/risk-off sẽ bổ sung ở bản cập nhật sau.)_

---

## 11. Định hướng Phase 2 — Auto Trade

Sau khi Phase 1 chạy ổn định và bạn theo dõi đủ số lệnh để tin tưởng độ chính xác, bước
tiếp theo sẽ là:

- Thêm module đặt lệnh tự động qua `MetaTrader5.order_send()`
- Quản lý SL/TP tự động, trailing stop
- Giới hạn số lệnh mở đồng thời, risk % mỗi lệnh

Phần này sẽ làm riêng khi bạn sẵn sàng — nhắn mình khi Phase 1 đã chạy ổn để mình dựng tiếp.

---

## 📎 Các file code đi kèm

Tất cả code khung sườn (`config.py`, `mt5_connector.py`, `strategy/*.py`, `telegram_bot.py`,
`groq_client.py`, `main.py`, `requirements.txt`) nằm trong cùng thư mục được gửi kèm tài liệu
này. Copy toàn bộ vào `C:\gold-bot\` theo đúng cấu trúc ở mục 6.
