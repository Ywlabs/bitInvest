"""멀티 타임프레임(주봉·일봉) 정렬."""

from __future__ import annotations

import pyupbit

from tools.indicators.ta_math import pct_change_from
from tools.indicators.types import MTFProfile


def _weekly_trend_label(
    price: float,
    weekly_ma200: float,
    weekly_ma200_slope_pct: float,
) -> str:
    if weekly_ma200 <= 0:
        return "neutral"
    if price < weekly_ma200 and weekly_ma200_slope_pct < -0.5:
        return "bear"
    if price > weekly_ma200 and weekly_ma200_slope_pct >= 0:
        return "bull"
    return "neutral"


def fetch_weekly_mtf(ticker: str, daily_price: float, daily_ma200: float) -> MTFProfile:
    """주봉 200MA 추세 + 일봉 정렬 점수."""
    df = pyupbit.get_ohlcv(ticker, interval="week", count=220)
    if df is None or len(df) < 30:
        return MTFProfile("neutral", 0.0, 0.0, 0.5, False)

    close = df["close"]
    price = float(close.iloc[-1])
    window = min(200, len(close))
    ma_series = close.rolling(window).mean()
    weekly_ma200 = float(ma_series.iloc[-1])
    ma_prev = float(ma_series.iloc[-5]) if len(ma_series) >= 5 else weekly_ma200
    slope_pct = pct_change_from(weekly_ma200, ma_prev)
    dist_pct = pct_change_from(price, weekly_ma200)
    trend = _weekly_trend_label(price, weekly_ma200, slope_pct)

    # 정렬 점수: 주봉·일봉 모두 200MA 위/아래 일치 시 1.0에 가깝게
    daily_above = daily_price > daily_ma200 if daily_ma200 else False
    weekly_above = price > weekly_ma200 if weekly_ma200 else False
    aligned = daily_above == weekly_above
    alignment = 0.85 if aligned and trend != "neutral" else (0.65 if aligned else 0.35)
    if trend == "bull" and daily_above:
        alignment = min(1.0, alignment + 0.1)
    if trend == "bear" and not daily_above:
        alignment = max(0.0, alignment - 0.15)

    return MTFProfile(
        weekly_trend=trend,
        weekly_dist_ma200_pct=dist_pct,
        weekly_ma200_slope_pct=slope_pct,
        alignment_score=round(alignment, 3),
        daily_weekly_aligned=aligned,
    )
