## 🗓 Cập nhật nhật ký — 2026-08-27

### Phát hiện: `main.py` (vòng lặp tín hiệu live) không lưu gì ra đĩa

Kiểm tra lại toàn bộ code thật (không chỉ dựa vào mô tả trong nhật ký) để trả lời câu hỏi
"Ctrl+C có làm mất dữ liệu không?". Kết quả kiểm tra từng file:

| File                      | Có ghi ra đĩa không?                                                      | Ctrl+C có mất dữ liệu không?                                                                                     |
| ------------------------- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `main.py` (tín hiệu live) | **Không — trước bản vá này**                                              | Có, nhưng không phải do Ctrl+C — vốn dĩ chưa từng lưu tín hiệu nào ra file. Chỉ có `print()` console + Telegram. |
| `sentiment_logger.py`     | Có, `sentiment_log.csv`                                                   | An toàn — mỗi lần ghi mở file → ghi → đóng ngay, không giữ file mở xuyên suốt.                                   |
| `calendar_fetcher.py`     | Không — chỉ cache RAM                                                     | Đúng thiết kế, không cần lưu (dữ liệu cần fetch lại mỗi lần dùng).                                               |
| `backtest.py`             | Có, nhưng chỉ ghi **sau khi xử lý xong toàn bộ** 1 lần chạy               | Ctrl+C giữa 1 lần chạy backtest → mất toàn bộ tiến độ của lần chạy đó.                                           |
| `run_batch_backtest.py`   | Gọi `backtest.py` cho từng offset, mỗi offset lưu xong mới sang offset kế | Chỉ mất offset đang dở dang, các offset trước đã lưu vẫn an toàn.                                                |

→ Đây chính là lỗ hổng cần vá trước khi tiếp tục để bot chạy dài ngày thu thập dữ liệu
(kế hoạch đối chiếu `sentiment_log.csv` với kết quả thắng/thua thật không thể thực hiện
được nếu không có lịch sử tín hiệu live).

### Đã vá: thêm `live_signal_logger.py` + patch `main.py`

- File mới `live_signal_logger.py`: ghi mỗi tín hiệu vào `live_signals_log.csv`
  (cột: `timestamp, direction, score, entry, sl, tp, reasons, sentiment_label,
sentiment_score`) — dùng đúng pattern an toàn đã có sẵn ở `sentiment_logger.py`
  (mở file → ghi 1 dòng → đóng ngay trong cùng block `with`, không giữ file mở).
- `main.py`: thêm 1 dòng import + gọi `live_signal_logger.log_signal(...)` **trước**
  bước gửi Telegram (để nếu Telegram lỗi mạng thì tín hiệu vẫn được lưu — xem mục dưới).
  Không đổi bất kỳ logic tính điểm/phân tích nào.

**Xác nhận với người dùng:** kể từ khi bản vá này được áp dụng vào `C:\gold-bot\` (không
phải từ trước đó, và không hồi tố được các tín hiệu live đã gửi trước ngày 2026-08-27),
Ctrl+C tại bất kỳ thời điểm nào cũng không làm mất tín hiệu đã gửi trước đó — mỗi tín hiệu
đã ghi thành công là nằm an toàn trên đĩa ngay khi ghi xong. Rủi ro lý thuyết còn lại
(Ctrl+C trúng đúng khoảnh khắc vài mili-giây đang ghi dở 1 dòng) gần như không đáng kể với
tần suất tín hiệu thưa hiện tại.

**Việc `backtest.py`/`run_batch_backtest.py` mất tiến độ giữa 1 lần chạy khi Ctrl+C — CHƯA
vá**, vì đây là quá trình chạy tay (không phải chạy nền 24/7), rủi ro thấp hơn nhiều so với
`main.py`. Có thể cân nhắc thêm checkpoint giữa chừng sau này nếu các lần backtest bắt đầu
chạy rất lâu (nhiều giờ).

### Lỗi gặp trong log: `telegram.error.NetworkError: httpx.ReadError`

Log cho thấy lỗi này xảy ra trong `_network_loop_retry` của `python-telegram-bot`, khi bot
đang polling để nhận tin nhắn chat 2 chiều (`chat_app.updater.start_polling()` trong
`main.py`). Đây là lỗi **mạng gián đoạn tạm thời** (mất kết nối 1 nhịp, đổi mạng, Windows
tạm ngủ card mạng...), không phải bug trong code của bot.

- Thư viện `python-telegram-bot` đã tự bắt lỗi này và tự động thử lại (đúng chức năng của
  `_network_loop_retry`) — không cần can thiệp gì thêm.
- Bằng chứng bot **không bị crash**: log cho thấy `sentiment_loop` và `analysis_loop` vẫn
  tiếp tục chạy bình thường ngay sau đó (`📰 Sentiment: BEARISH...`, `Chưa đủ điều kiện
entry...`) — 2 vòng lặp chính hoàn toàn không bị ảnh hưởng bởi lỗi polling Telegram.
- Nếu lỗi này lặp lại **rất thường xuyên** (vài phút/lần), đáng kiểm tra lại độ ổn định
  mạng của máy đang chạy bot (wifi có đang chập chờn, VPN, hoặc máy có bị Windows tạm ngắt
  card mạng khi ở chế độ tiết kiệm pin không) — nhưng xuất hiện thỉnh thoảng như trong log
  hiện tại là bình thường, không cần sửa code.

### Việc cần làm tiếp theo

- [x] ~~Kiểm tra bot có lưu dữ liệu tín hiệu live ra đĩa không~~ → phát hiện KHÔNG, đã vá
      bằng `live_signal_logger.py`
- [ ] Copy `live_signal_logger.py` (file mới) và `main.py` (đã sửa) vào `C:\gold-bot\`,
      restart bot
- [ ] Theo dõi `live_signals_log.csv` được tạo ra và ghi đúng mỗi khi có tín hiệu mới
- [ ] Tiếp tục để bot chạy, gom đủ 30-50+ tín hiệu live đã ngã ngũ trước khi đối chiếu
      với `sentiment_log.csv` và cân nhắc bước tiếp theo (xem tiêu chí ở lần trao đổi
      trước: win rate live nên nằm trong/gần CI 54.3–69.6% của backtest)

============================================================================================================================================

## 🗓 Cập nhật nhật ký — 2026-08-28 (buổi kiểm tra code + sửa lỗi múi giờ)

### Bối cảnh

Bạn đã gửi lại toàn bộ code hiện tại (main.py, calendar*fetcher.py, news_fetcher.py,
sentiment*\*.py, live_signal_logger.py, telegram_bot.py, config liên quan...) để hỏi:
"đang chạy bot lấy dữ liệu thực, trong lúc này có cần code/sửa gì không?"

Đã kiểm tra toàn bộ file:

- ✅ Syntax tất cả file đều sạch, không lỗi
- ✅ Luồng ghi dữ liệu hợp lý: `live_signal_logger.log_signal()` gọi TRƯỚC khi gửi
  Telegram (nếu Telegram lỗi mạng, tín hiệu vẫn được lưu)
- ✅ 2 vòng lặp (`analysis_loop` + `sentiment_logger.sentiment_loop()`) độc lập nhau qua
  `asyncio.gather()`, lỗi ở vòng lặp phụ không làm crash vòng lặp chính
- ⚠️ Phát hiện 1 lỗi thật cần sửa ngay: **múi giờ trong lịch kinh tế sai** (chi tiết dưới)

---

### 🐛 Lỗi phát hiện: `calendar_fetcher.py` tính sai giờ sự kiện +4 tiếng

**Nguyên nhân:** code giả định giờ trong file XML lịch ForexFactory là giờ Mỹ (Eastern
Time, `CALENDAR_ASSUMED_TZ`), nhưng thực ra **giờ trong file là UTC**.

**Cách phát hiện — đối chiếu trực tiếp với ảnh chụp forexfactory.com/calendar thật:**

| Sự kiện                          | Trên forexfactory.com (giờ VN thật) | Code tính ra (trước khi sửa) | Chênh lệch |
| -------------------------------- | ----------------------------------- | ---------------------------- | ---------- |
| Core PCE Price Index m/m (26/08) | 19:30                               | 23:30                        | **+4 giờ** |
| Prelim GDP q/q (26/08)           | 19:30                               | 23:30                        | **+4 giờ** |

4 giờ chênh lệch này khớp chính xác với offset EDT (Mỹ, mùa hè) so với UTC — xác nhận
100% nguyên nhân: code coi giờ UTC là giờ Mỹ nên cộng dư 4 tiếng khi quy đổi sang giờ VN.

**Đã sửa:** thêm dòng sau vào `.env` (không cần sửa code, vì `config.py` đọc biến này
qua `os.getenv()` nên `.env` luôn được ưu tiên):

```env
CALENDAR_ASSUMED_TZ=UTC
```

**Đã xác nhận sửa đúng:** chạy lại `python calendar_fetcher.py` sau khi thêm dòng trên,
Core PCE Price Index m/m giờ hiện đúng **19:30 (+0700)** — khớp chính xác với
forexfactory.com thật.

**Ảnh hưởng của lỗi này trước khi sửa:** chỉ ảnh hưởng đến tính năng cảnh báo "sắp có
tin ảnh hưởng cao" đính kèm tin nhắn Telegram (Phase 1.5b) — có thể đã cảnh báo sai giờ
suốt vài ngày bot chạy. **Không ảnh hưởng** đến `live_signals_log.csv`, `sentiment_log.csv`,
hay logic tính điểm confluence — những phần quan trọng nhất cho việc đối chiếu win rate
sau này vẫn hoàn toàn chính xác.

---

### ✅ Không có gì khác cần sửa — tiếp tục chạy bot bình thường

Sau khi thêm `CALENDAR_ASSUMED_TZ=UTC` vào `.env`, toàn bộ hệ thống đã đúng. Không cần
code hay sửa gì thêm trong giai đoạn thu thập dữ liệu hiện tại.

**Lưu ý nhỏ, không cấp bách (để dành sau, không cần làm bây giờ):** `calendar_fetcher.py`
và `news_fetcher.py` gọi `requests.get()` đồng bộ (blocking) bên trong vòng lặp `async`.
Mỗi lần tải mới (lịch: 1 giờ/lần, tin tức: 30 phút/lần), toàn bộ event loop có thể tạm
"đứng hình" vài giây đến tối đa ~40s nếu mạng chậm — bot không bị lỗi hay mất dữ liệu,
chỉ tạm thời không phản hồi chat Telegram trong khoảnh khắc đó. Có thể sửa sau bằng
`asyncio.to_thread()` nếu thấy phiền, không cần làm ngay.

---

### Việc cần làm tiếp theo

- [x] ~~Kiểm tra toàn bộ code hiện tại có lỗi gì không~~ → tìm thấy 1 lỗi múi giờ, đã sửa
- [x] ~~Sửa lỗi múi giờ lịch kinh tế~~ → xong, đã xác nhận đúng
- [ ] Tiếp tục để bot chạy, gom đủ tối thiểu 30-50 tín hiệu live đã ngã ngũ (lý tưởng
      80-100+) trong `live_signals_log.csv`
- [ ] Khi đủ mẫu: đối chiếu win rate live với khoảng tin cậy backtest (62.3%,
      CI 54.3–69.6%, n=151) và timeout rate (~33%) — đây là tiêu chí đã thống nhất để
      quyết định có đi tiếp hay không
- [ ] Song song: đối chiếu `sentiment_log.csv` với kết quả thắng/thua thật để quyết định
      có nên đưa sentiment vào `MIN_CONFLUENCE_SCORE` hay không (chưa làm, cần đủ dữ liệu)
