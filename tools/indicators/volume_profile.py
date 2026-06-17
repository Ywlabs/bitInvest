"""거래량·OBV·VWAP 프로필."""

from __future__ import annotations

import pandas as pd

from tools.indicators.ta_math import obv, pct_change_from, rolling_vwap
from tools.indicators.types import VolumeProfile


def build_volume_profile(df: pd.DataFrame, price: float) -> VolumeProfile:
    close = df["close"]
    volume = df["volume"]
    vol_avg = float(volume.rolling(20).mean().iloc[-1]) if len(volume) >= 20 else float(volume.iloc[-1])
    vol_today = float(volume.iloc[-1])
    volume_ratio = (vol_today / vol_avg) if vol_avg else 1.0

    obv_series = obv(close, volume)
    obv_10_ago = float(obv_series.iloc[-11]) if len(obv_series) >= 11 else float(obv_series.iloc[0])
    obv_now = float(obv_series.iloc[-1])
    obv_slope = pct_change_from(obv_now, obv_10_ago)

    vwap = float(rolling_vwap(df, 20).iloc[-1])
    dist_vwap = pct_change_from(price, vwap)

    last = df.iloc[-1]
    prev_close = float(close.iloc[-2]) if len(close) >= 2 else price
    ret_1d = pct_change_from(price, prev_close)
    body = abs(float(last["close"]) - float(last["open"]))
    full_range = float(last["high"]) - float(last["low"])
    lower_wick = min(float(last["open"]), float(last["close"])) - float(last["low"])
    wick_ratio = (lower_wick / full_range) if full_range else 0.0

    capitulation = ret_1d < -2.0 and volume_ratio >= 1.5 and wick_ratio >= 0.45
    accumulation = ret_1d > 0 and volume_ratio >= 1.1 and obv_slope > 0 and dist_vwap < 0

    return VolumeProfile(
        volume_ratio=volume_ratio,
        obv_slope_10d_pct=obv_slope,
        capitulation=capitulation,
        accumulation=accumulation,
        vwap_20d=vwap,
        dist_vwap_pct=dist_vwap,
    )
