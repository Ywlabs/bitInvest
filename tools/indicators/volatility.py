"""변동성 레짐·Drawdown 프로필."""

from __future__ import annotations

import pandas as pd

from tools.indicators.ta_math import pct_change_from, percentile_rank, realized_volatility, wilder_atr
from tools.indicators.types import DrawdownProfile, VolatilityProfile


def classify_volatility_regime(atr_ratio: float) -> str:
    if atr_ratio >= 2.0:
        return "extreme"
    if atr_ratio >= 1.5:
        return "high"
    if atr_ratio <= 0.75:
        return "low"
    return "normal"


def build_volatility_profile(df: pd.DataFrame, price: float, close: pd.Series) -> VolatilityProfile:
    atr_series = wilder_atr(df, 14)
    atr_14 = float(atr_series.iloc[-1])
    atr_14_pct = (atr_14 / price * 100) if price else 0.0
    atr_avg = float(atr_series.rolling(60).mean().iloc[-1]) if len(atr_series) >= 60 else atr_14
    atr_ratio = (atr_14 / atr_avg) if atr_avg else 1.0

    from tools.indicators.ta_math import bollinger_bands

    _, _, _, pct_b, bandwidth = bollinger_bands(close, 20, 2.0)
    bb_pct_b = float(pct_b.iloc[-1])
    bb_bw = float(bandwidth.iloc[-1])

    rv = realized_volatility(close, 20)
    rv_last = float(rv.iloc[-1]) if not rv.empty else 0.0
    rv_pct = float(percentile_rank(rv, 60).iloc[-1]) if len(rv) >= 60 else 50.0

    return VolatilityProfile(
        atr_14=atr_14,
        atr_14_pct=atr_14_pct,
        atr_ratio=atr_ratio,
        bb_pct_b=bb_pct_b,
        bb_bandwidth_pct=bb_bw,
        realized_vol_20d=rv_last,
        vol_percentile_60d=rv_pct,
        regime=classify_volatility_regime(atr_ratio),
    )


def build_drawdown_profile(close: pd.Series, price: float) -> DrawdownProfile:
    window_52w = min(365, len(close))
    window_slice = close.iloc[-window_52w:]
    high_52w = float(window_slice.max())
    low_52w = float(window_slice.min())
    high_ath = float(close.max())

    dd_52w = pct_change_from(price, high_52w)
    dd_ath = pct_change_from(price, high_ath)
    recovery = pct_change_from(price, low_52w) if low_52w else 0.0

    return DrawdownProfile(
        drawdown_52w_pct=dd_52w,
        drawdown_ath_pct=dd_ath,
        recovery_from_52w_low_pct=recovery,
    )
