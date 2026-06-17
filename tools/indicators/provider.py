"""업비트 OHLCV 수집."""

from __future__ import annotations

import pandas as pd
import pyupbit

from tools.indicators.errors import IndicatorError


def fetch_ohlcv(ticker: str, interval: str = "day", count: int = 400) -> pd.DataFrame:
    df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
    if df is None or df.empty:
        raise IndicatorError(f"{ticker} OHLCV 수집 실패 ({interval})")
    return df
