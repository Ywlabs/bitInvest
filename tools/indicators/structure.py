"""가격 구조(스윙 고저, 지지/저항) 분석."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tools.indicators.ta_math import pct_change_from
from tools.indicators.types import StructureProfile


def _local_extrema(series: pd.Series, window: int = 5) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """로컬 스윙 고점·저점 (인덱스, 가격)."""
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    arr = series.to_numpy()
    n = len(arr)
    half = window // 2
    for i in range(half, n - half):
        seg = arr[i - half : i + half + 1]
        val = arr[i]
        if val == seg.max() and val > seg[0] and val > seg[-1]:
            highs.append((i, float(val)))
        if val == seg.min() and val < seg[0] and val < seg[-1]:
            lows.append((i, float(val)))
    return highs, lows


def analyze_structure(df: pd.DataFrame, price: float, lookback: int = 120) -> StructureProfile:
    """최근 스윙 구조로 bias·지지/저항 추정."""
    segment = df.tail(lookback)
    highs, lows = _local_extrema(segment["high"], window=5)

    support = float(segment["low"].min())
    resistance = float(segment["high"].max())

    higher_low = False
    lower_high = False
    if len(lows) >= 2:
        higher_low = lows[-1][1] > lows[-2][1]
    if len(highs) >= 2:
        lower_high = highs[-1][1] < highs[-2][1]

    if higher_low and not lower_high:
        bias = "bullish"
    elif lower_high and not higher_low:
        bias = "bearish"
    else:
        bias = "range"

    dist_support = pct_change_from(price, support)
    dist_resistance = pct_change_from(price, resistance)
    near_support = dist_support <= 3.0 and dist_support >= -8.0

    return StructureProfile(
        bias=bias,
        higher_low=higher_low,
        lower_high=lower_high,
        support=support,
        resistance=resistance,
        dist_support_pct=dist_support,
        dist_resistance_pct=dist_resistance,
        near_support=near_support,
    )
