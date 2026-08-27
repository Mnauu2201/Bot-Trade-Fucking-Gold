# """
# mt5_connector.py — Kết nối MetaTrader 5 và lấy dữ liệu nến đa khung thời gian
# """

# import MetaTrader5 as mt5
# import pandas as pd
# from config import Config

# TIMEFRAME_MAP = {
#     "M1": mt5.TIMEFRAME_M1,
#     "M5": mt5.TIMEFRAME_M5,
#     "M15": mt5.TIMEFRAME_M15,
#     "H1": mt5.TIMEFRAME_H1,
#     "H4": mt5.TIMEFRAME_H4,
#     "D1": mt5.TIMEFRAME_D1,
# }


# class MT5Connector:
#     def __init__(self):
#         self.connected = False

#     def connect(self):
#         if not mt5.initialize(
#             login=Config.MT5_LOGIN,
#             password=Config.MT5_PASSWORD,
#             server=Config.MT5_SERVER,
#         ):
#             error = mt5.last_error()
#             raise ConnectionError(f"Không kết nối được MT5: {error}")

#         self.connected = True
#         account_info = mt5.account_info()
#         print(f"✅ Đã kết nối MT5 — Tài khoản: {account_info.login}, "
#               f"Balance: {account_info.balance} {account_info.currency}")
#         return account_info

#     def disconnect(self):
#         mt5.shutdown()
#         self.connected = False

#     def get_candles(self, timeframe: str, count: int = 200) -> pd.DataFrame:
#         """Lấy dữ liệu nến cho 1 khung thời gian, trả về DataFrame."""
#         tf = TIMEFRAME_MAP.get(timeframe)
#         if tf is None:
#             raise ValueError(f"Timeframe không hợp lệ: {timeframe}")

#         rates = mt5.copy_rates_from_pos(Config.MT5_SYMBOL, tf, 0, count)
#         if rates is None or len(rates) == 0:
#             raise RuntimeError(f"Không lấy được dữ liệu nến cho {timeframe}")

#         df = pd.DataFrame(rates)
#         df["time"] = pd.to_datetime(df["time"], unit="s")
#         df.rename(columns={
#             "open": "open", "high": "high", "low": "low",
#             "close": "close", "tick_volume": "volume"
#         }, inplace=True)
#         return df[["time", "open", "high", "low", "close", "volume"]]

#     def get_current_price(self) -> dict:
#         tick = mt5.symbol_info_tick(Config.MT5_SYMBOL)
#         if tick is None:
#             raise RuntimeError("Không lấy được giá hiện tại")
#         return {"bid": tick.bid, "ask": tick.ask, "time": tick.time}

#     def get_all_timeframes(self) -> dict:
#         """Lấy dữ liệu cho tất cả khung thời gian dùng trong confluence scoring."""
#         return {
#             "H4": self.get_candles("H4", 200),
#             "H1": self.get_candles("H1", 200),
#             "M15": self.get_candles("M15", 200),
#             "M5": self.get_candles("M5", 200),
#             "M1": self.get_candles("M1", 100),
#         }


"""
mt5_connector.py — Kết nối MetaTrader 5 và lấy dữ liệu nến đa khung thời gian
"""

import MetaTrader5 as mt5
import pandas as pd
from config import Config

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


class MT5Connector:
    def __init__(self):
        self.connected = False

    def connect(self):
        if not mt5.initialize(
            login=Config.MT5_LOGIN,
            password=Config.MT5_PASSWORD,
            server=Config.MT5_SERVER,
        ):
            error = mt5.last_error()
            raise ConnectionError(f"Không kết nối được MT5: {error}")

        self.connected = True
        account_info = mt5.account_info()
        print(f"✅ Đã kết nối MT5 — Tài khoản: {account_info.login}, "
              f"Balance: {account_info.balance} {account_info.currency}")
        return account_info

    def disconnect(self):
        mt5.shutdown()
        self.connected = False

    def get_candles(self, timeframe: str, count: int = 200, offset: int = 0) -> pd.DataFrame:
        """
        Lấy dữ liệu nến cho 1 khung thời gian, trả về DataFrame.

        offset: số nến lùi lại trước khi bắt đầu đếm count nến (0 = tính từ nến
        mới nhất hiện tại). Dùng offset > 0 để lấy các đoạn lịch sử xa hơn,
        tránh lúc nào cũng chỉ test đúng N nến gần nhất — quan trọng để backtest
        qua nhiều giai đoạn thị trường khác nhau (trend/sideway/giảm) chứ không
        chỉ mỗi giai đoạn hiện tại.
        """
        tf = TIMEFRAME_MAP.get(timeframe)
        if tf is None:
            raise ValueError(f"Timeframe không hợp lệ: {timeframe}")

        rates = mt5.copy_rates_from_pos(Config.MT5_SYMBOL, tf, offset, count)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"Không lấy được dữ liệu nến cho {timeframe}")

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.rename(columns={
            "open": "open", "high": "high", "low": "low",
            "close": "close", "tick_volume": "volume"
        }, inplace=True)
        return df[["time", "open", "high", "low", "close", "volume"]]

    def get_current_price(self) -> dict:
        tick = mt5.symbol_info_tick(Config.MT5_SYMBOL)
        if tick is None:
            raise RuntimeError("Không lấy được giá hiện tại")
        return {"bid": tick.bid, "ask": tick.ask, "time": tick.time}

    def get_all_timeframes(self) -> dict:
        """Lấy dữ liệu cho tất cả khung thời gian dùng trong confluence scoring."""
        return {
            "H4": self.get_candles("H4", 200),
            "H1": self.get_candles("H1", 200),
            "M15": self.get_candles("M15", 200),
            "M5": self.get_candles("M5", 200),
            "M1": self.get_candles("M1", 100),
        }