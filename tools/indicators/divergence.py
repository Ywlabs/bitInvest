"""RSI·MACD 다이버전스 탐지."""

from __future__ import annotations

import pandas as pd

from tools.indicators.structure import _local_extrema
from tools.indicators.types import DivergenceProfile


def detect_divergence(
    close: pd.Series,
    rsi: pd.Series,
    macd_hist: pd.Series,
    lookback: int = 60,
) -> DivergenceProfile:
    """
    최근 스윙 저점/고점 기준 다이버전스.

    - 강세: 가격 저점 하락 + RSI 저점 상승
    - 약세: 가격 고점 상승 + RSI 고점 하락
    """
    segment_close = close.tail(lookback)
    segment_rsi = rsi.tail(lookback)
    segment_macd = macd_hist.tail(lookback)

    _, lows = _local_extrema(segment_close, window=5)
    highs, _ = _local_extrema(segment_close, window=5)

    rsi_bull = False
    rsi_bear = False
    macd_bull = False

    if len(lows) >= 2:
        i1, p1 = lows[-2]
        i2, p2 = lows[-1]
        r1 = float(segment_rsi.iloc[i1])
        r2 = float(segment_rsi.iloc[i2])
        m1 = float(segment_macd.iloc[i1])
        m2 = float(segment_macd.iloc[i2])
        if p2 < p1 and r2 > r1:
            rsi_bull = True
        if p2 < p1 and m2 > m1:
            macd_bull = True

    if len(highs) >= 2:
        i1, p1 = highs[-2]
        i2, p2 = highs[-1]
        r1 = float(segment_rsi.iloc[i1])
        r2 = float(segment_rsi.iloc[i2])
        if p2 > p1 and r2 < r1:
            rsi_bear = True

    return DivergenceProfile(
        rsi_bullish=rsi_bull,
        rsi_bearish=rsi_bear,
        macd_bullish=macd_bull,
    )
