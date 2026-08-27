# 📒 Tiến độ Phase 1.5 — Module tin tức + Sentiment + Lịch kinh tế

Ghi lại để tiếp tục ở phiên Claude khác nếu cần.

---

## Mục tiêu Phase 1.5 (theo checklist gốc)

Module crawl tin tức vĩ mô/dầu + Groq sentiment, chạy song song với vòng lặp phân tích
giá chính — **KHÔNG cộng vào MIN_CONFLUENCE_SCORE ngay**, chỉ log lại để sau này đối
chiếu với kết quả thắng/thua thật, tránh lặp lại rủi ro overfit đã gặp ở Phase 1.

---

## Các file đã tạo/sửa (tổng hợp từ đầu Phase 1.5)

### File MỚI

| File                    | Vai trò                                                                                                                                                                                                                                                                                                         |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `news_fetcher.py`       | Lấy tin tức từ RSS (FXStreet + investingLive), lọc theo từ khoá + thời gian gần đây, loại trùng tiêu đề. Dùng `requests` (không để feedparser tự tải) + User-Agent giả trình duyệt + retry 2 lần khi timeout. **Đã xác nhận chạy đúng — xem mục "Trạng thái hiện tại" bên dưới.**                               |
| `sentiment_analyzer.py` | Gửi tin tức đã lấy cho Groq, trả về JSON có cấu trúc: `bullish/bearish/neutral` + điểm số -1..1 + lý do ngắn. Có fallback "neutral" an toàn nếu Groq lỗi hoặc không có tin.                                                                                                                                     |
| `sentiment_logger.py`   | Vòng lặp nền (`sentiment_loop()`), chạy song song với vòng lặp phân tích giá qua `asyncio.gather()` trong `main.py`. Cứ mỗi `NEWS_CHECK_INTERVAL_SECONDS` (mặc định 30 phút) tự lấy tin + chấm sentiment + ghi vào `sentiment_log.csv`. Cache sentiment gần nhất để `main.py` lấy ra khi gửi tín hiệu Telegram. |
| `calendar_fetcher.py`   | Lấy lịch kinh tế ForexFactory (tin "đỏ"/High impact) qua mirror XML của Fair Economy. Lọc sự kiện High impact liên quan USD trong vài giờ tới, cache 1 giờ. **Đã xác nhận chạy đúng — xem mục "Trạng thái hiện tại" bên dưới.**                                                                                 |

### File ĐÃ SỬA

| File               | Thay đổi                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `config.py`        | Thêm `NEWS_RSS_FEEDS`, `NEWS_KEYWORDS`, `NEWS_LOOKBACK_HOURS`, `NEWS_CHECK_INTERVAL_SECONDS` (cho tin tức/sentiment) và `CALENDAR_XML_URL`, `CALENDAR_CURRENCIES`, `CALENDAR_LOOKAHEAD_HOURS`, `CALENDAR_CACHE_TTL_SECONDS` (cho lịch kinh tế). Tất cả đều có giá trị mặc định, không bắt buộc phải khai báo trong `.env`. `_DEFAULT_NEWS_FEEDS` hiện tại: `fxstreet.com/rss/news` + `investinglive.com/feed` (xem lịch sử đổi feed bên dưới). |
| `main.py`          | Chạy song song `analysis_loop()` (chính) + `sentiment_logger.sentiment_loop()` (phụ) qua `asyncio.gather()`. Khi có tín hiệu, lấy sentiment gần nhất + lịch tin sắp tới rồi truyền vào `telegram_bot.send_signal()`.                                                                                                                                                                                                                           |
| `telegram_bot.py`  | `send_signal()` nhận thêm tham số `sentiment` và `upcoming_events` (đều optional). Gửi thêm 1-2 tin nhắn Telegram phụ: sentiment (ghi rõ "chỉ tham khảo, không ảnh hưởng điểm số") và cảnh báo tin sắp tới (ghi rõ "cân nhắc, không tự động huỷ tín hiệu").                                                                                                                                                                                    |
| `requirements.txt` | Thêm `feedparser==6.0.11` và `requests==2.32.3`.                                                                                                                                                                                                                                                                                                                                                                                               |
| `news_fetcher.py`  | `_parse_published()`: sửa bug `time.mktime()` → `calendar.timegm()` (chi tiết ở mục dưới).                                                                                                                                                                                                                                                                                                                                                     |

---

## Nguyên tắc quan trọng đã thống nhất (đừng phá vỡ)

1. **Sentiment và lịch tin đều CHỈ mang tính cảnh báo/tham khảo** — không tự động cộng
   điểm hay chặn tín hiệu. Lý do: tránh lặp lại rủi ro overfit như đã xảy ra khi chỉnh
   `confluence.py` — mọi thay đổi ảnh hưởng đến việc CÓ gửi tín hiệu hay không đều phải
   qua backtest kiểm chứng trước, không chỉnh "cảm tính".
2. Khi nào muốn nâng cấp sentiment/lịch tin thành yếu tố ảnh hưởng thật đến điểm số,
   cần: (a) thu thập đủ lâu để có dữ liệu `sentiment_log.csv`, (b) đối chiếu với
   `backtest_report_*.csv` theo timestamp, (c) backtest lại có/không có yếu tố đó để
   so sánh — đúng quy trình đã áp dụng cho OB/FVG/price action ở Phase 1.

---

## ✅ Trạng thái hiện tại (2026-08-27) — cả 3 phần chạy đúng, đã kiểm chứng bằng log thật

| Module/thành phần     | Trạng thái | Bằng chứng                                                                                       |
| --------------------- | ---------- | ------------------------------------------------------------------------------------------------ |
| `news_fetcher.py`     | ✅ Xong    | 20-22 tin liên quan/6h, cả 2 feed HTTP 200                                                       |
| `calendar_fetcher.py` | ✅ Xong    | Parse đúng 69 sự kiện, lọc đúng High+USD, quy đổi timezone đúng                                  |
| Groq sentiment (live) | ✅ Xong    | `main.py` chạy live cho ra sentiment thật (BEARISH -0.60, lý do hợp lý) thay vì fallback neutral |

Chi tiết quá trình chẩn đoán và sửa lỗi — **đọc phần này trước khi nghi ngờ lại các module
trên**, để không lặp lại các bước chẩn đoán đã làm:

### 1. Lỗi mạng ban đầu (ISP chặn theo SNI) — ảnh hưởng `news_fetcher.py`, KHÔNG ảnh hưởng `calendar_fetcher.py`

Log ban đầu: `fxstreet.com`, `dailyforex.com`, `investinglive.com` đều lỗi
`ConnectionResetError`/`Read timed out` khi chạy `news_fetcher.py`. Quá trình loại trừ:

- Server (Claude) fetch `fxstreet.com/rss/news` thành công ngay lần đầu → feed không chết.
- Kaspersky: mục "Do not scan encrypted connections" đã bật sẵn từ trước → loại trừ
  Kaspersky MITM traffic.
- Test trực tiếp bằng Chrome trên máy Windows đó → cũng bị `ERR_CONNECTION_RESET` trên
  `fxstreet.com` → xác nhận vấn đề nằm ở tầng mạng của máy/ISP, không liên quan gì đến
  Python/code/thư viện.
- Đổi DNS sang `8.8.8.8`/`1.1.1.1` (chỉ đổi DNS server) → **không đủ**, vẫn lỗi. Lý do:
  DNS đúng nhưng ISP vẫn đọc được tên miền ở bước TLS ClientHello (SNI) và chặn/reset tại
  đó — đổi DNS server thường không ẩn được SNI, khác với DNS-over-HTTPS/VPN thật.
- Test chéo xác nhận: điện thoại qua wifi nhà → lỗi; điện thoại bật app 1.1.1.1 (WARP) qua
  cùng wifi → vào được; điện thoại qua 4G nhà mạng khác → vào được. → 100% là chặn ở tầng
  ISP/wifi nhà, theo domain, dựa trên SNI — không phải do site chết, không phải do máy.

**Đã xử lý:** cài Cloudflare WARP (`https://1.1.1.1/`) trên Windows, bật chế độ
"1.1.1.1 with WARP" — WARP mã hoá toàn bộ traffic qua tunnel nên ISP không đọc được SNI
để chặn nữa. Sau khi bật WARP, cả `fxstreet.com` và `investinglive.com` tải HTTP 200 ổn định.

**QUAN TRỌNG — đừng suy rộng quá mức:** khi test `calendar_fetcher.py` (domain
`nfs.faireconomy.media`) sau đó, module này chạy đúng ngay từ đầu, KHÔNG gặp lỗi mạng nào —
tức là không phải mọi domain nước ngoài đều bị ISP chặn kiểu này. Đã có lúc suy đoán nhầm
(ghi trong nhật ký cũ) rằng lỗi cũ của `calendar_fetcher.py` là do domain `cdn-nfs...` đổi
tên miền — suy đoán đó **không sai nhưng không phải nguyên nhân chính khiến nó "đang lỗi"
ở thời điểm ghi nhật ký đó**; thực tế khi test lại với domain mới, module chạy trơn tru
không cần WARP. Bài học: mỗi domain/lỗi cần tự kiểm chứng riêng, không áp dụng máy móc
kết luận từ domain khác.

**Việc cần nhớ khi vận hành:** WARP cần được **bật mỗi khi chạy bot 24/7** trên máy này để
`news_fetcher.py` hoạt động — nếu tắt WARP, lỗi mạng có thể quay lại. Cân nhắc để WARP tự
khởi động cùng Windows nếu chạy bot dài hạn không có người canh.

### 2. Bug thật trong code (đã sửa) — sai timezone khi parse thời gian đăng tin

Sau khi hết lỗi mạng, `news_fetcher.py` vẫn báo "Tìm thấy 0 tin liên quan" dù tải được
30-55 mục thô mỗi lần chạy. Nguyên nhân — bug ở `_parse_published()`:

- feedparser trả `published_parsed` là `time.struct_time` **đã ở giờ UTC** (chuẩn RSS).
- Code cũ dùng `time.mktime(struct)` để quy đổi sang epoch timestamp — nhưng `mktime()`
  diễn giải struct_time đầu vào là **giờ local của máy chạy code**, không phải UTC.
- Máy chạy bot ở giờ Việt Nam (UTC+7) → mỗi tin bị tính sai lệch ~7 tiếng so với UTC thật.
- Với `NEWS_LOOKBACK_HOURS` mặc định chỉ 6 giờ, hầu như toàn bộ tin thật (dù vừa đăng) bị
  cutoff loại bỏ oan — khớp chính xác với triệu chứng "có mục thô nhưng 0 tin liên quan".

**Đã sửa:** đổi `time.mktime(struct)` → `calendar.timegm(struct)` trong
`_parse_published()` (diễn giải đúng struct_time là UTC, không áp offset timezone máy).
Thêm `import calendar` ở đầu file.

**Đã kiểm chứng:** sau khi sửa bug + đổi feed (mục 3 dưới) + bỏ `NEWS_RSS_FEEDS` cứng
trong `.env`, kết quả cuối cùng: **20 tin liên quan** trong 6 giờ gần nhất, gồm tin gold
trực tiếp và tin Fed/lãi suất (Jackson Hole, BOJ Himino, Fed hike bets). Cả 2 feed HTTP 200
ổn định. Coi như xong hoàn toàn, không cần sửa thêm trừ khi feed nguồn đổi cấu trúc.

### 3. Feed chết — đã thay

`dailyforex.com/rss/forexnews.xml` xác nhận trả về HTTP 404 thật (không phải bị chặn) —
feed đã đổi URL hoặc bị gỡ bỏ. Đã bỏ khỏi `_DEFAULT_NEWS_FEEDS` trong `config.py`, thay
bằng `investinglive.com/feed` (feed chính, nhiều tin gold/Fed hơn feed
`/feed/centralbank/` cũ). Người dùng đã xoá dòng `NEWS_RSS_FEEDS` cứng trong `.env` để
dùng đúng default mới.

### 4. `calendar_fetcher.py` — chạy đúng, không có bug

Chạy thử (WARP đang bật, dù có vẻ không cần thiết cho domain này) → tải XML thành công,
parse đúng 69 sự kiện trong tuần, lọc đúng High-impact + USD, quy đổi timezone Eastern
Time → giờ VN (+0700) chính xác. Kết quả "0 sự kiện trong cửa sổ lọc 2 giờ tới" tại thời
điểm test là **đúng thực tế thị trường**, không phải lỗi — sự kiện High-impact gần nhất
(Fed Chairman Warsh Speaks) còn cách 33.7 giờ, ngoài `CALENDAR_LOOKAHEAD_HOURS=2` mặc định.
Không cần sửa gì thêm.

---

## ⚠️ Lưu ý cho phiên Claude mới (đọc trước khi bắt đầu)

1. **Đừng đọc phần "Vấn đề chưa giải quyết" của các bản nhật ký cũ hơn (nếu còn sót) như
   sự thật hiện tại** — cả `news_fetcher.py` và `calendar_fetcher.py` đã được xác nhận
   chạy đúng bằng log thật ở trên. Nếu người dùng báo lỗi lại, đây là **hồi quy mới**, xử
   lý như vấn đề mới, không phải tiếp tục vấn đề cũ.
2. **Nếu người dùng báo lỗi mạng (ConnectionReset/timeout) trên bất kỳ domain nào**: hỏi
   ngay xem Cloudflare WARP có đang bật không trước khi đoán nguyên nhân khác. Đây là bot
   chạy từ Việt Nam, ISP có xu hướng chặn một số domain tài chính nước ngoài theo SNI —
   nhưng **không phải domain nào cũng bị**, nên vẫn cần kiểm chứng bằng cách fetch thử
   (web_fetch) trước khi kết luận, không suy diễn từ domain khác.
3. **Quy trình chẩn đoán đã dùng hiệu quả** (áp dụng lại nếu gặp lỗi mạng tương tự):
   (a) tự fetch thử domain đó xem có sống không, (b) loại trừ Kaspersky/antivirus bằng
   cách kiểm tra cấu hình thật (đừng giả định), (c) yêu cầu người dùng test bằng trình
   duyệt thật trên cùng máy, (d) nếu trình duyệt cũng lỗi → test chéo qua mạng khác (4G)
   để xác định ISP-level block, (e) nếu xác nhận ISP chặn → hướng dẫn WARP thay vì chỉ đổi
   DNS (đổi DNS thường không đủ vì SNI vẫn lộ).
4. **Bug timezone (`time.mktime` vs `calendar.timegm`) là loại lỗi dễ tái diễn** — nếu
   thêm bất kỳ module mới nào xử lý `datetime`/`struct_time` từ nguồn bên ngoài (feed RSS,
   API khác), kiểm tra kỹ xem hàm quy đổi có đang ngầm định giờ local máy hay không, đặc
   biệt vì máy chạy bot ở UTC+7 — lỗi loại này im lặng (không crash) nhưng làm sai lệch dữ
   liệu, khó phát hiện nếu không có log kiểu "N mục thô nhưng 0 tin liên quan".
5. **Đã sửa 3 file**: `news_fetcher.py` (bug timezone), `config.py` (đổi feed list +
   đổi `GROQ_MODEL`) — tất cả đã được người dùng áp dụng và xác nhận qua log thật.
6. **`.env` luôn ghi đè default trong `config.py`** — khi đổi bất kỳ giá trị mặc định nào
   trong `config.py` (dạng `os.getenv("X", "default_mới")`), PHẢI chủ động nhắc người dùng
   kiểm tra `.env` xem có dòng `X=...` cứng đang tồn tại hay không, vì `os.getenv` luôn ưu
   tiên biến môi trường đã set. Lỗi này đã xảy ra 2 lần trong phiên trước (`NEWS_RSS_FEEDS`
   và `GROQ_MODEL`) — người dùng phải tự phát hiện và comment dòng cũ trong `.env` cả 2
   lần vì Claude không hỏi trước. Đừng lặp lại lỗi này.

---

## Việc cần làm tiếp theo

- [x] ~~Xác nhận `news_fetcher.py` chạy ổn định, thấy tin tức thật hiện ra~~ → xong, 20 tin
- [x] ~~Xác nhận `calendar_fetcher.py` chạy được~~ → xong, parse đúng 69 sự kiện, lọc đúng
- [x] ~~Chạy `main.py` để xác nhận cả 2 module hoạt động đúng, không crash vòng lặp chính~~
      → xong 2026-08-27, MT5 kết nối OK, vòng lặp phân tích giá chạy bình thường,
      `sentiment_logger` không làm crash bot dù Groq lỗi — fallback neutral hoạt động
      đúng thiết kế. Phát hiện thêm 1 vấn đề riêng, xem mục dưới.
- [x] ~~Chạy lại `main.py` sau khi đổi `GROQ_MODEL` để xác nhận sentiment thật~~ → xong,
      cần comment dòng `GROQ_MODEL=llama-3.3-70b-versatile` cứng trong `.env` trước (xem
      chi tiết ở mục "Groq model deprecated" bên dưới), sau đó sentiment thật hoạt động
      đúng: BEARISH score=-0.60 dựa trên tin Fed hike bets/USD mạnh — hợp lý, đã xong hẳn
- [x] ~~Để bot chạy vài tuần thu thập `sentiment_log.csv`~~ → **có thể bắt đầu ngay**, mọi
      thành phần (giá + tin tức + sentiment + lịch kinh tế) đã xác nhận chạy đúng cùng lúc
- [ ] Sau khi có đủ `sentiment_log.csv` (vài tuần), đối chiếu với kết quả backtest để
      quyết định có nên đưa sentiment vào `MIN_CONFLUENCE_SCORE` hay không (theo đúng
      nguyên tắc đã thống nhất ở mục "Nguyên tắc quan trọng" phía trên) — CHƯA làm bước
      này, đây là việc còn lại duy nhất của Phase 1.5

---

## Cập nhật 2026-08-27 (tiếp) — Groq model `llama-3.3-70b-versatile` đã bị deprecate

Khi chạy `main.py` lần đầu, log báo lỗi:

```
Error code: 404 - {'error': {'message': 'The model `llama-3.3-70b-versatile` does not
exist or you do not have access to it.', ...}}
```

Bot KHÔNG bị crash — `sentiment_logger.py` có fallback "neutral" đúng thiết kế, nên vòng
lặp phân tích giá chính vẫn chạy bình thường. Nhưng sentiment log lúc này chỉ toàn giá trị
neutral giả, không phản ánh tin tức thật — cần sửa trước khi để bot thu thập
`sentiment_log.csv` dài hạn.

**Nguyên nhân đã xác nhận qua tài liệu Groq chính thức (console.groq.com/docs/models):**
Groq đã chuyển `llama-3.3-70b-versatile` và `llama-3.1-8b-instant` sang diện **Enterprise
only** — không còn khả dụng ở tier Free/Developer thông thường mà key GROQ_API_KEY hiện tại
đang dùng. Đây không phải lỗi cấu hình hay lỗi mạng, mà do Groq đổi chính sách model.

**Đã sửa:** đổi `GROQ_MODEL` mặc định trong `config.py` từ `llama-3.3-70b-versatile` sang
`openai/gpt-oss-120b` — model production hiện tại của Groq, cùng tầm context window
(131,072 tokens), tốc độ nhanh (~500 t/sec), giá rẻ ($0.15/$0.60 mỗi 1M token input/output).
Đã kiểm tra: cả `groq_client.py` và `sentiment_analyzer.py` đều đọc model qua
`Config.GROQ_MODEL`, không hardcode riêng — nên chỉ cần sửa 1 dòng trong `config.py` là đủ
áp dụng cho toàn bộ hệ thống (chat, explain_signal, sentiment analysis).

**Lưu ý cho phiên Claude mới:** nếu `openai/gpt-oss-120b` sau này cũng bị deprecate hoặc đổi
tên, kiểm tra lại danh sách model hiện tại tại `https://console.groq.com/docs/models` hoặc
gọi `GET https://api.groq.com/openai/v1/models` bằng chính GROQ_API_KEY của người dùng để
lấy danh sách model họ thực sự có quyền truy cập — đừng đoán tên model từ trí nhớ huấn
luyện, vì Groq đổi model/chính sách khá thường xuyên (bằng chứng: đã đổi ít nhất 1 lần
trong khoảng thời gian ngắn giữa lúc `.env` được cấu hình lần đầu và lúc lỗi này xuất hiện).

**Đã kiểm chứng bằng log thật (2026-08-27):** sau khi áp dụng `config.py` mới, chạy lại
`python main.py` vẫn còn lỗi — vì `.env` của người dùng có dòng cứng
`GROQ_MODEL=llama-3.3-70b-versatile` **đè lên** giá trị mặc định trong `config.py`
(`os.getenv("GROQ_MODEL", default)` luôn ưu tiên biến môi trường nếu có). Người dùng đã
comment dòng đó lại trong `.env`, chạy lại → sentiment thật xuất hiện:

```
📰 Sentiment: BEARISH (score=-0.60, 22 tin) — Các tin về USD mạnh lên do kỳ vọng tăng
lãi suất Fed và dữ liệu lạm phát hỗ trợ đồng USD làm áp lực giảm giá vàng...
```

Lý do phân tích hợp lý, khớp với nội dung tin thật đang có (Fed hike bets, PCE inflation).
**Coi như xong hoàn toàn** — không còn fallback neutral giả, sentiment log giờ phản ánh
tin tức thật.

**Lưu ý quan trọng cho phiên Claude mới:** khi sửa bất kỳ giá trị mặc định nào trong
`config.py` dạng `os.getenv("X", "default_mới")`, luôn nhắc người dùng kiểm tra `.env` xem
có dòng `X=...` cứng đang ghi đè hay không — sửa code không tự động có tác dụng nếu `.env`
đã set giá trị riêng. Đây là lỗi đã lặp lại 2 lần trong phiên này (lần 1 với
`NEWS_RSS_FEEDS`, lần 2 với `GROQ_MODEL`) — nên hỏi chủ động ngay khi đổi bất kỳ default
nào, thay vì đợi người dùng tự phát hiện.

**Bằng chứng log thật (`sentiment_log.csv`, người dùng gửi lại sau đó) khớp đúng trình tự
đã sửa — 4 dòng đầu tiên của file là dấu vết trực tiếp của toàn bộ quá trình debug:**

```
14:13:50  neutral, 0 tin   — trước khi sửa bug timezone (0 tin do time.mktime() sai lệch)
15:25:37  neutral, 21 tin, lỗi Groq 404  — đã sửa news_fetcher, chưa đổi GROQ_MODEL
15:27:33  neutral, 22 tin, lỗi Groq 404  — đã đổi config.py nhưng .env còn đè GROQ_MODEL cũ
15:28:11  bearish -0.60, 22 tin  — sau khi comment dòng .env, sentiment thật đầu tiên
```

Nếu thấy các dòng neutral/lỗi này còn sót trong `sentiment_log.csv` khi phân tích dữ liệu
sau này (đối chiếu với backtest), nên lọc bỏ 3 dòng đầu (14:13–15:27) vì đó là nhiễu do
lỗi cấu hình lúc setup, không phải tín hiệu sentiment thật — dữ liệu sentiment đáng tin bắt
đầu từ dòng `15:28:11` trở đi.

### File đã sửa thêm trong phiên này

| File        | Thay đổi                                                                                                                   |
| ----------- | -------------------------------------------------------------------------------------------------------------------------- |
| `config.py` | `GROQ_MODEL` mặc định: `llama-3.3-70b-versatile` → `openai/gpt-oss-120b` (model cũ đã bị Groq chuyển sang Enterprise-only) |
