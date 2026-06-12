"""기술적 지표 (RSI, MACD, 이동평균)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import pyupbit


class IndicatorError(Exception):
    """지표 계산 실패."""


@dataclass
class TechnicalSnapshot:
    """일봉 기준 기술적 지표 묶음."""

    rsi_14: float
    macd: float
    macd_signal: float
    macd_hist: float
    macd_hist_prev: float
    ma_60: float
    ma_120: float
    ma_200: float
    price: float
    return_7d_pct: float
    return_30d_pct: float
    dist_ma200_pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "rsi_14": self.rsi_14,
            "macd": self.macd,
            "macd_signal": self.macd_signal,
            "macd_hist": self.macd_hist,
            "macd_hist_prev": self.macd_hist_prev,
            "ma_60": self.ma_60,
            "ma_120": self.ma_120,
            "ma_200": self.ma_200,
            "price": self.price,
            "return_7d_pct": self.return_7d_pct,
            "return_30d_pct": self.return_30d_pct,
            "dist_ma200_pct": self.dist_ma200_pct,
        }


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def fetch_technical_snapshot(ticker: str = "KRW-BTC", count: int = 220) -> TechnicalSnapshot:
    """업비트 일봉 OHLCV 로 지표 계산."""
    df = pyupbit.get_ohlcv(ticker, interval="day", count=count)
    if df is None or len(df) < 60:
        raise IndicatorError(f"{ticker} 일봉 데이터 부족")

    close = df["close"]
    price = float(close.iloc[-1])

    rsi_series = _rsi(close, 14)
    rsi_14 = float(rsi_series.iloc[-1])

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line

    ma_60 = float(close.rolling(60).mean().iloc[-1])
    ma_120 = float(close.rolling(120).mean().iloc[-1])
    ma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else ma_120

    price_7d_ago = float(close.iloc[-8]) if len(close) >= 8 else price
    price_30d_ago = float(close.iloc[-31]) if len(close) >= 31 else price
    return_7d = (price / price_7d_ago - 1) * 100 if price_7d_ago else 0.0
    return_30d = (price / price_30d_ago - 1) * 100 if price_30d_ago else 0.0
    dist_ma200 = (price / ma_200 - 1) * 100 if ma_200 else 0.0

    return TechnicalSnapshot(
        rsi_14=rsi_14,
        macd=float(macd_line.iloc[-1]),
        macd_signal=float(signal_line.iloc[-1]),
        macd_hist=float(hist.iloc[-1]),
        macd_hist_prev=float(hist.iloc[-2]),
        ma_60=ma_60,
        ma_120=ma_120,
        ma_200=ma_200,
        price=price,
        return_7d_pct=return_7d,
        return_30d_pct=return_30d,
        dist_ma200_pct=dist_ma200,
    )
